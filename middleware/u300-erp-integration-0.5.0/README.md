# Integrasi Reader U300 — 0.5 LAB

**ERP Kain Nussantara**  
**Production IT: PT Kubus Teknologi Indonesia**  
19 Oktober 2026

## Status dan isi paket

Paket kumulatif perubahan ERP terhadap commit `055f7ea0f852582867b3ab063d28e7e41f67f410`. Belum di-push atau diterapkan pada produksi. Paket Android yang kompatibel tetap **U300 Agent 0.4.0 LAB**; tidak ada perubahan binary Android pada iterasi ini.

- `erp-u300-v2.patch`: seluruh perubahan ERP, bukan hanya selisih dari paket 0.4.
- `erp-files/`: salinan file untuk pemeriksaan.
- `KN_U300_Agent_0.4.0_LAB_2026-10-19.zip`: sumber reader, APK LAB, dokumentasi dan evidence pengujian reader sebelumnya.
- `evidence/`: hasil tes integrasi pada versi ERP ini.
- `MANIFEST.json`: baseline, status verifikasi, dan hash file.
- `REVIEW.md`: hasil review, batas implementasi, dan pekerjaan berikutnya.

## Fitur yang tersedia

API reader menyediakan profil konfigurasi, penerimaan event dengan ACK setelah penyimpanan MongoDB, penutupan lintasan idempotent, status gate dan telemetry. Event pembacaan tidak mengubah stok, kepemilikan atau pencatatan keuangan.

Panel operasional berada pada **Perangkat RFID → perangkat reader/gate → Integrasi reader U300**. Operator memilih sumber dari SJ, transfer fisik atau putaway. Pengunggahan profil mengikuti hak admin ERP yang ada.

### Tambahan pada 0.5

1. Satu lintasan keluar dapat mencakup **1–20 SJ** dari gudang reader yang sama, maksimal 2.000 roll keseluruhan. Setiap SJ tetap memiliki identitas sendiri. Gabungan ini adalah konteks pemeriksaan gate, bukan pembuatan dokumen dispatch baru.
2. Semua roll gabungan harus terbaca. Dokumen tidak aktif, keanggotaan berubah, roll kurang/lebih atau konteks pergerakan berbeda tidak menghasilkan clearance hijau.
3. Pencegahan pembacaan ulang disimpan berdasarkan dokumen asli, arah dan roll. Mengganti kelompok SJ tidak menghapus jejak lintasan sebelumnya.
4. Riwayat tersedia per halaman, dengan urutan yang tetap membedakan lintasan bertimestamp sama. Indeks database mengikuti urutan tersebut.
5. Operator berizin dapat mengunduh JSON bukti lintasan, meliputi snapshot manifest, event, keputusan dan tindak lanjut yang tersimpan. Unduhan tidak mengubah data. Kunci idempotensi internal tidak disertakan.
6. Akses manifest, riwayat terkait dokumen, ekspor dan acknowledge memeriksa cakupan entitas sumber. Device key tidak dapat mengekspor bukti atau mengakui pemeriksaan alarm.

## Alur operator

1. Daftarkan perangkat dan gudangnya melalui fasilitas perangkat ERP. Terbitkan key melalui mekanisme yang tersedia.
2. Unggah profil commissioning yang sesuai perangkat dan lokasi. Jangan menyatakan perangkat commissioned sebelum pengujian hardware.
3. Buka panel U300, pilih arah dan jenis dokumen. Centang SJ yang benar-benar akan melewati gate bersamaan, lalu pilih **Gunakan dokumen**.
4. Jalankan capture pada reader. Lintasan yang sudah dimulai mempertahankan snapshot manifestnya; perubahan pilihan berlaku bagi lintasan baru.
5. Periksa hasil cocok/kurang/lebih dan alasan keputusan. Hanya respons ERP yang memenuhi syarat freshness dan kelengkapan dapat menjadi sinyal hijau hidup pada reader.
6. Jika alarm tertahan, periksa fisik dan dokumen terlebih dahulu, kemudian catat pemeriksaan. Reset alarm tidak mengubah keputusan lama menjadi hijau dan tidak menghapus crossing claim.
7. Gunakan halaman riwayat dan **Unduh bukti lintasan** untuk penelusuran.

## Validasi versi ini

| Pemeriksaan | Hasil |
|---|---|
| Integrasi router/service ERP dengan MongoDB lokal | 53 assertion lulus |
| Gabungan SJ, pagination dan hak akses pengguna asli | 34 assertion lulus |
| Java reader melalui HTTPS ke API ERP lokal | 9 assertion lulus |
| Parsing JSX dua komponen RFID | Lulus |
| Patch pada baseline bersih | Lihat evidence/patch-check.log |

Pengujian menggunakan database lokal terisolasi, bukan database bisnis. Tes hak akses memakai sesi pengguna, matriks izin dan middleware cakupan entitas ERP. Ini belum menguji seluruh bootstrap aplikasi, interaksi browser atau U300 fisik. Pengujian reader 0.4 terdahulu tersedia di paket reader; tidak dihitung sebagai tes Android runtime pada iterasi ini.

## Penerapan development

1. Simpan pekerjaan lain dan cocokkan baseline. Pada baseline yang lebih baru, review konflik terlebih dahulu.
2. Jalankan `git apply --check erp-u300-v2.patch`, kemudian apply hanya jika pemeriksaan berhasil. Jika paket 0.4 sudah diterapkan, jangan mengaplikasikan patch kumulatif ini langsung; lakukan perbandingan/merge terhadap file hasil 0.5.
3. Pasang dependency backend repo termasuk jsonschema. Startup membuat indeks non-TTL. Tidak ada migrasi penghapusan riwayat.
4. Jalankan `backend/tests/run_rfid_v2_integration.py` dan `backend/tests/run_rfid_v2_extended.py` dengan `MONGO_URL` database lokal khusus. Masing-masing membuat database uji baru.
5. Jalankan `backend/tests/run_u300_https.py` dengan argumen direktori sumber Agent 0.4, JDK 17, jar org.json, dan direktori output tes. Sertifikat lokal tes bukan sertifikat produksi.
6. Build frontend dalam lingkungan dependency standar repo, lalu uji panel di browser memakai role dan cakupan gudang/entitas sebenarnya.
7. Lanjutkan integrasi staging dan commissioning hardware sebelum mengizinkan penggunaan operasional.

## Titik selesai produksi

Penerimaan produksi membutuhkan build frontend penuh, acceptance UI dan role di staging, uji perangkat nyata termasuk RF/sensor/GPIO/boot/offline/restart, prosedur pemulihan crossing salah, serta signing dan distribusi produksi. Paket ini menyelesaikan pengembangan dan tes lokal yang dijelaskan di atas, belum memenuhi seluruh syarat produksi.
