# Custom role dan pengujian ulang R&D — rancangan implementasi rinci

ERP Kain Nussantara · Produksi IT PT Kubus Teknologi Indonesia  
16 Oktober 2026 · Paket revisi 1.3 · LN-015 / LN-034

## Keputusan dan batas pemeriksaan

Owner menetapkan hasil pengujian ulang yang gagal menunggu keputusan PIC berwenang. Jangan otomatis menghentikan produksi, menonaktifkan artikel, membatalkan stok atau kontrak. Hasil gagal tetap gagal; persetujuan tindak lanjut bukan perubahan fakta hasil pengujian. Siklus gagal belum boleh menjadi bukti kelulusan baru sebelum tindak lanjut yang sah. Pengaruh keputusan terhadap supplier/dokumen tertentu harus eksplisit, bukan global tanpa dasar.

Pemeriksaan ulang bersifat source review snapshot 64d81f29577dae4daa86ddc64689dec7243804f2. Belum merupakan uji browser, audit seluruh endpoint atau verifikasi HEAD terbaru. L00 wajib rebase dan inventaris implementasi aktual. Rancangan di bawah adalah target implementasi, bukan klaim fitur sudah selesai.

## Yang sudah ada dan yang belum cukup

| Sumber | Kondisi yang terbaca |
|---|---|
| frontend/src/features/settings/entities/RoleModuleRow.jsx | Modul menggunakan Tidak ada/Lihat saja/Kelola penuh, termasuk indikator sebagian dan panel lanjutan. |
| frontend/src/features/settings/entities/RoleAdvancedPanel.jsx | Aktivitas per resource tersedia; pilih aksi menyalakan Lihat, mencabut Lihat mematikan aksi halaman. Belum merupakan pohon eksplisit Modul/Menu/Submenu/Tab/Aktivitas. |
| frontend/src/features/settings/entities/RoleEditorDrawer.jsx | Ada salin role, preview menu, akun, notifikasi dan ringkasan perubahan. Reuse komponen yang sesuai, jangan membuang fondasi ini. |
| backend/access_modules.py | Modul mengelompokkan resources dan nav. R&D memakai resource rnd untuk beberapa menu uji; pengelompokan tampilan tidak membuktikan pemisahan izin tiap uji. |
| backend/services/custom_role_service.py | permission_settings.matrix dinyatakan sumber izin; jangan menambahkan matrix kedua yang berbeda untuk pohon UI. |
| backend/routers/rnd.py | Banyak operasi menggunakan rnd/create, submit, assess, decide. Perlu pemetaan rinci ke objek/jenis uji dan kebijakan service, bukan sekadar mengubah label UI. |
| backend/services/rnd_sample_service.py | prepare_revalidation menolak proofing; decide_sample meminta harga dan dapat membuat kontrak purchase. Guard duplikat revalidation berdasarkan produk/jenis uji belum membedakan supplier. |
| backend/services/color_service.py | Ringkasan rnd_supplier berasal dari keputusan terbaru. Ini tidak cukup untuk daftar hasil kelayakan semua supplier. |

LN-010 sebelumnya sudah memuat arah empat tingkat, tetapi tiga acceptance umumnya belum cukup menjadi petunjuk implementasi rinci. LN-015 memperinci pekerjaan dan UAT; LN-034 memperinci revalidation, bukan mengganti seluruh aturan R&D.

## Struktur layar hak akses

Navigasi target: Pengaturan → Role & Hak Akses → pilih/buat role. Pastikan route aktual pada handoff.

1. Daftar role: nama, deskripsi, profil kerja, jumlah pengguna, status, perubahan terakhir; cari/filter dan aksi salin. Tidak menampilkan ID teknis sebagai label utama.
2. Identitas: nama dan tujuan role, template asal bila disalin. Mengganti nama tidak mengubah capability. Pengguna ditugaskan melalui mekanisme akun existing.
3. Hak aktivitas: pohon empat tingkat Modul → Menu → Submenu/Tab → Aktivitas. Untuk menu tanpa submenu, aktivitas langsung di bawah menu; jangan membuat tingkat kosong.
4. Cakupan data: entitas, lokasi, gudang, lini/kategori, serta own/team/all bila didukung kebutuhan modul. Tampilkan batas role dan batas akun/dokumen serta hasil irisan efektif. Hak melihat stok agregat Sales tidak otomatis membuka identitas entitas pemilik.
5. Visibilitas informasi: kolom/atribut sensitif, termasuk grade, harga beli, biaya, margin dan informasi supplier sesuai domain. Izin export tidak otomatis membuka semua field. Larangan grade pada profil Sales termasuk trial tetap berlaku menurut LN-012.
6. Preview efektif: pilih konteks akun/entitas/lokasi/lini; tampilkan menu dan aksi yang boleh/tidak, field tersembunyi, serta alasannya. Preview read-only, tidak menyamar menjadi akun lain atau menjalankan transaksi.
7. Review perubahan: izin ditambah/dicabut, perubahan scope, akun terdampak dan konflik; simpan atomik dengan audit/version. Jika versi role berubah oleh admin lain, tampilkan konflik dan minta muat ulang/rekonsiliasi, jangan overwrite diam-diam.

Gunakan area editor lebar atau halaman tersendiri bila drawer tidak cukup. Pohon dapat dilipat, pencarian mempertahankan breadcrumb; panel kanan menjelaskan aktivitas terpilih. Toolbar pencarian dan ringkasan perubahan mudah ditemukan. Label utama memakai bahasa kerja: “Catat hasil handfeel”, “Setujui hasil proofing”, bukan hanya assess/decide.

### Perilaku centang dan preset

- Induk menampilkan tidak ada/sebagian/semua berdasarkan aktivitas anak yang relevan. Parent adalah pengelompokan, bukan hak baru yang membuka backend tanpa leaf permission.
- Preset Lihat saja/Kelola tetap boleh sebagai jalan pintas. Tampilkan daftar dampak sebelum menerapkan; jangan menyembunyikan pencabutan/pemberian hak detail di balik preset.
- Pilih semua saat filter aktif harus jelas menyebut hanya hasil filter atau seluruh cabang; pilih satu semantik konsisten, default yang disarankan hanya hasil terlihat. Ringkasan harus mencantumkan jumlah dan daftar perubahan.
- Memilih aksi yang membutuhkan Lihat menjelaskan dependency dan menambahkan hak baca minimum objek tersebut. Jangan membuka seluruh modul, data keuangan atau jenis uji lain.
- Aktivitas baru setelah upgrade tidak otomatis menjadi granted karena user dulu memilih Kelola penuh. Migrasi harus eksplisit; template tidak menjadi wildcard masa depan.
- Tombol tidak tersedia karena kurang hak dibedakan dari tombol belum bisa dijalankan karena status dokumen. Alasan tidak boleh membocorkan data yang tidak berhak dilihat.
- Keyboard, fokus, label checkbox, indikator sebagian dan pesan error harus berfungsi tanpa bergantung warna. Hindari font sangat kecil pada daftar aktivitas; uji viewport desktop/tablet dan zoom.

## Registry dan hak minimum yang dipisahkan

Satu registry canonical menghubungkan permission ID stabil dengan modul/menu/tab, label/deskripsi, tipe objek, aksi, dependency, scope dan field policy. UI dan backend memakai sumber yang sama. Nama teknis final mengikuti repo; daftar berikut adalah kontrak kemampuan, bukan kewajiban membuat resource duplikat.

| Area | Kemampuan yang harus bisa diberikan terpisah |
|---|---|
| R&D | Lihat histori; buat uji; pilih supplier; kirim sample; buka round; input hasil; ACC teknis per labdip/proofing/handfeel; putus tindak lanjut gagal; rilis master. |
| Designer | Buat/revisi/upload; checklist paper; ACC desain; lepas HOLD; lihat rapor/nilai desain. |
| Special Order | Buat/ubah; catat keputusan customer; PIC; harga/Special Price; pilih rute supplier/makloon; realisasi PR; pembatalan/amandemen. |
| Kontrak | Lihat; referensikan kontrak; buat; ubah/amandemen; persetujuan sesuai status existing. ACC teknis tidak memberi hak kontrak otomatis. |
| MD Quality / QC | Pilih roll; input hasil MDQ; input inspect; keputusan/pelepasan yang sah; tidak mencampur kedua proses. |
| Sales | Checkout; ubah alokasi/roll; harga khusus; persetujuan; grade/customer policy sesuai profil dan hak. |
| WMS | Receiving; tag/reprint/retag; putaway; reserve/issue; transfer; dispatch; opname dan persetujuan selisih, dengan scope lokasi/gudang. |
| Retur / Finance | Pengajuan, penerimaan, inspeksi, disposition, pengganti, kompensasi, kredit/refund, retur antar-entitas/supplier serta posting/pembayaran sesuai domain dan keputusan yang sudah jelas. |
| Export / konfigurasi | Baca dataset/kolom, preview, download, rapor; kelola role, assignment, policy dan audit dengan hak terpisah. |

Tabel ini daftar minimum, bukan klaim seluruh endpoint sudah terpetakan. Agent harus menghasilkan inventory lengkap seluruh fase: path menu/tab, aktivitas, endpoint/service/event, izin existing, izin target, scope/field, sumber aturan, migrasi dan test ID. Setiap aksi tanpa mapping menjadi blocker penutupan domain terkait. Customisasi berarti admin dapat menyusun role dari aktivitas yang tersedia; bukan membuat operasi backend baru secara bebas.

Izin efektif = grant aktivitas yang sah ∩ scope akun/role ∩ scope objek ∩ field policy ∩ prasyarat workflow. Audit deny, role fallback, superadmin/system worker dan aturan approval service existing agar tidak bertentangan dengan matrix. Jangan mengasumsikan mendukung multi-role; jika ada, dokumentasikan prioritas/konflik; jika hanya single-role, pertahankan tanpa memperluas scope secara tersembunyi.

Custom role baru harus dapat menjadi PIC tanpa nama staf atau nama role literal di kode. PIC yang satu sudah ACC cukup; keputusan atomik. Namun hak PIC R&D tidak otomatis memberi ACC Designer, Finance atau kontrak. Assignment tugas bukan permission; keduanya diperiksa sesuai workflow.

Hak diperiksa pada server untuk list/detail/mutasi/bulk/export/job, bukan hanya menyembunyikan menu. Cache/session harus mengikuti versi perubahan hak. Pembatasan field juga berlaku pada payload, pencarian, filter facet, agregasi dan file unduhan. Preview menu wajib ditopang evaluasi izin efektif, bukan hanya daftar nav yang dikonfigurasi.

## Pengujian ulang R&D dan keputusan PIC

Flow target: produk/varian existing → pilih supplier dan alasan siklus → pilih jenis uji → acuan spesifikasi/artwork/warna/handfeel → round → hasil → keputusan teknis atau menunggu PIC → tindak lanjut yang eksplisit.

- Produk tetap satu. Simpan supplier, produk/varian, versi acuan, siklus dan jenis uji sebagai konteks hasil. Proofing existing bukan desain baru. Perubahan motif mengikuti aturan Special Order/redesign yang sudah disepakati.
- Supplier A dan B memiliki hasil terpisah. Supplier sama boleh memiliki siklus ulang yang sah; deduplikasi berdasarkan request/siklus, bukan melarang seluruh uji jenis sama pada produk tanpa konteks.
- Simpan histori lengkap sebagai record pengujian. Ringkasan pada master bukan SSOT tunggal dan tidak boleh menjadi satu supplier pemenang yang menghapus kelayakan supplier lain. Bila ringkasan dibatasi jumlah baris, detail/pagination tetap mengakses histori penuh.
- Pisahkan hasil teknis dari kontrak. Tidak wajib harga untuk revalidation teknis. Kontrak existing dapat direferensikan setelah validasi produk/supplier/entitas/jenis, tanpa update tarif atau masa berlaku. Kontrak baru/amandemen merupakan aksi lain dengan haknya sendiri.
- Hasil gagal memunculkan antrean “Menunggu keputusan PIC”, berisi hasil, alasan, bukti, acuan terdahulu dan dokumen yang berkaitan. PIC memilih tindak lanjut yang didukung flow existing, misalnya uji ulang atau keputusan operasional beralasan; jangan mengarang dampak global.
- Keputusan mencatat pelaku, waktu, alasan, objek/cakupan dan tindakan lanjutan. Gagal tidak berubah menjadi ACC karena PIC membaca atau menutup notifikasi. Override jika tersedia harus terpisah dan auditable.
- Dokumen/stok lama tidak otomatis dibatalkan. Ketika sebuah pengadaan baru mensyaratkan kelulusan uji baru, hasil gagal yang masih menunggu tidak dapat dipakai sebagai bukti lulus. Jangan menafsirkan “menunggu PIC” sebagai membolehkan semua produksi baru secara otomatis.
- Hubungkan hasil ke LN-033 sesuai produk/supplier/versi. Supplier makloon dan supplier barang jadi dapat memakai hasil teknis yang relevan, tetapi kontrak pengadaannya tetap berbeda.

## Implementasi, migrasi dan titik selesai

L00 memetakan route/schema/permission actual dan menyelesaikan kontrak evaluator. L01/LN-015 memperluas registry, enforcement, editor dan preview dengan reuse fondasi existing. L03/LN-034 memperluas revalidation dan antrean keputusan PIC, menggunakan permission L01. L14 menguji seluruhnya pada kandidat final.

Migrasikan matrix lama dengan snapshot sebelum/sesudah, daftar akun terdampak, mapping izin generik ke rinci dan daftar kasus ambigu untuk review. Jangan default grant semua aktivitas baru atau menghilangkan akses existing tanpa laporan. Hindari lockout administrator lewat prosedur migrasi/recovery yang diuji. Role terkunci dan akses sistem dipetakan secara eksplisit. Simpan audit perubahan assignment, izin dan scope. Role edit bersamaan dan retry harus aman.

Handoff wajib menyertakan inventory permission seluruh modul, desain layar dan screenshot aktual, tabel request/response/enforcement, migrasi/dry-run, hasil semua acceptance LN-015/LN-034 serta regresi LN-010/LN-012/LN-033. Uji minimal role MD woven, MD printing, PIC teknis, pengelola kontrak, Sales, Admin Sales, admin gudang lokasi terbatas dan export terbatas sebagai fixture; nama fixture bukan nama role wajib bisnis.

Kelulusan mensyaratkan pemisahan aktivitas terbukti melalui UI dan API, scope/field konsisten, preview sesuai realitas, perubahan hak berlaku saat session aktif, serta pengguna dapat menyelesaikan tugas konfigurasi tanpa membaca ID teknis. Build atau screenshot pohon saja tidak cukup. Status seluruh tambahan tetap not_started/not_run sampai bukti implementasi dan review tersedia.
