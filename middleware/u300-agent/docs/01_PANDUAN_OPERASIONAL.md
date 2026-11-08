# Panduan pemasangan dan penggunaan

ERP Kain Nussantara · PT Kubus Teknologi Indonesia

## A. Menjalankan simulasi tanpa reader

1. Pasang APK pada perangkat Android ARM API 30 atau lebih baru; ARM64 direkomendasikan. Emulator harus mendukung ABI ARM APK ini (atau translasi ARM yang sesuai), bukan sembarang emulator x86. Mode default adalah simulasi. U300 belum diperlukan untuk mode ini.
2. Buka **KN U300 Agent · LAB**. Pada tindakan pemeliharaan pertama buat PIN 6–12 angka. Lima kegagalan PIN mengunci pemeriksaan selama satu menit.
3. Tekan **Mulai layanan**. Layanan mengambil konfigurasi dari simulator internal, membuka penyimpanan simulasi, dan menampilkan radio ready serta ERP online. Layanan tetap berjalan setelah layar aplikasi ditutup.
4. Isi EPC contoh pada **Laboratorium simulasi**, lalu tekan **Simulasikan pembacaan tag**. Setiap penekanan mencatat satu observasi baru; pengulangan EPC tidak dihapus dari jejak observasi.
5. Tunggu idle tiga detik atau tekan **Tutup lintasan secara manual**. Agent mengirim observasi, menunggu ACK durable, lalu meminta penutupan dan mengambil gate-state.
6. Untuk skenario penolakan, pilih RED, tekan **Pakai keputusan simulasi**, lalu kirim tag pada lintasan berikutnya. Penguncian terlihat sampai **Simulasikan supervisor melepas red latch** dipilih. Tombol ini hanya tersedia di simulasi.
7. Untuk skenario offline, aktifkan checkbox offline sebelum kirim tag. Observasi tersimpan lokal. Setelah online lagi antrean dikirim, tetapi lintasan tersebut tidak boleh menyalakan green.
8. **Simulasikan EPC tidak valid** menghasilkan observasi karantina. Status ini tidak dianggap telah lolos validasi barang.
9. **Histori lintasan & diagnosis** menampilkan jejak tersimpan. **Ekspor diagnosis JSON** menyimpan file melalui pemilih lokasi Android. Diagnosis tidak menyertakan device key/PIN, tetapi mengandung identitas lintasan dan hasil keputusan.

Simulasi menggunakan keputusan yang dipilih operator sebagai respons tiruan; ia tidak memeriksa manifest, kepemilikan, stok, atau SO nyata. Green pada simulator bukan bukti bahwa ERP telah mengizinkan pengiriman.

## B. Menyiapkan U300 nyata

1. Pastikan firmware, Android, SDK, antena, catu daya, sensor, dan wiring sesuai hasil commissioning.
2. Hentikan layanan sebelum membuka **Konfigurasi & provisioning**.
3. Nonaktifkan mode simulasi. Masukkan origin ERP, misalnya `https://erp.example.com`, logical gate ID, dan device key khusus perangkat. Tidak menerima URL HTTP, kredensial dalam URL, path tambahan, query, atau fragment.
4. Simpan. Device key disimpan terenkripsi dengan kunci Android Keystore. Jika kolom key kosong pada pembaruan, key lama dipertahankan.
5. ERP harus menyediakan DeviceConfig yang valid dengan `agent_profile=kn-u300-v1`, `commissioned=true`, `expected_region_code`, dan `expected_antenna_power_dbm` hasil pemeriksaan perangkat. Template contoh sengaja belum memenuhi commissioning.
6. Mulai layanan. Jika pemeriksaan region/power/antena gagal, agent menghentikan capture; jangan mengubah profil hanya untuk menghilangkan pesan tanpa memeriksa perangkat.
7. Setelah UAT boot berhasil, pilihan mulai otomatis setelah reboot dapat diaktifkan. Uji juga pembatasan background/battery dari firmware vendor.

## C. Arti kontrol dan status

| Kontrol/status | Makna |
|---|---|
| Jeda capture | Menutup capture aktif dan menghentikan radio; pengiriman antrean tetap berjalan |
| Lanjutkan capture | Mengaktifkan kembali capture jika tidak ada blok identitas/kontrak |
| Hentikan layanan | Menghentikan layanan Android; data lokal dipertahankan |
| Menunggu kirim | Event yang belum mendapat ACK durable |
| Karantina | Event ditolak/ditandai ERP; bukan data yang boleh dihapus atau dianggap sukses |
| UNKNOWN | Tidak ada clearance live yang sah; bukan izin bergerak |
| RED | Gate-state menyatakan penguncian aktif |
| GREEN | Keputusan ERP final dan memenuhi pengaman lokal untuk manifest penuh |

PIN adalah otorisasi pemeliharaan lokal, bukan pengganti role ERP. Persetujuan supervisor untuk melepas latch dilakukan di ERP dengan identitas pengguna; tidak menggunakan device key.

## D. Penanganan gangguan

- **401/403:** hentikan layanan, periksa device registration/key di ERP, perbarui provisioning dengan tujuan ERP dan gate yang sama. Jangan mengalihkan antrean ke perangkat lain.
- **400/409:** ekspor diagnosis dan perbaiki request/versi di sisi ERP; gunakan Pemulihan koneksi / kontrak untuk mencoba ulang dengan ID asli. Jika penyebab belum selesai, blok muncul kembali. Perubahan versi config yang valid menunggu antrean lama selesai sebelum diterapkan.
- **Antrean penuh:** pulihkan koneksi/kapasitas lebih dahulu. Tidak ada pembuangan otomatis data lama. Kebijakan arsip/retensi belum disetujui.
- **SDK/GPIO gagal:** hentikan pergerakan berdasarkan sinyal agent; periksa koneksi dan lakukan commissioning ulang. Log software tidak membuktikan lampu fisik benar-benar berubah.
- **Restart saat lintasan terbuka:** lintasan ditandai INTERRUPTED dan tidak lengkap; tidak menerima clearance live dari proses lama. Ulangi lintasan sesuai SOP setelah pemeriksaan fisik.
