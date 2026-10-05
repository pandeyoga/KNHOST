# Audit lanjutan: kontrol periode, pengaturan, dan inspeksi

Baseline `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`. Hasil 29 September 2026. Lanjutan dari [18–21](18_HASIL_PENGUJIAN_INTEGRASI.md); temuan IX01–IX06 tetap berada di laporan 19.

**Tambahan ini memuat empat cacat terkonfirmasi (IX07–IX10), satu gap kebijakan inspeksi, dan sembilan skenario baru.** Tiga skenario adalah kontrol positif/penolakan yang bekerja. Seluruh skenario memakai service asli dan MongoDB lokal; pengaturan serta otorisasi periode juga melalui FastAPI/ASGI. Tidak ada perubahan source aplikasi atau akses data produksi.

Harness dan hasil: [integration_round5.py](integration_repro/integration_round5.py), [hasil JSON](integration_repro/integration_round5.json). Test race hanya mengatur urutan pembacaan/penulisan asli, bukan mengganti hasil query dengan data tiruan. Fixture awal merupakan data sintetis; seluruh lifecycle setup bisnis tidak dijalankan melalui UI.

## Hasil test bawaan

Tiga berkas test asli juga dijalankan: `test_uom_1_13.py` (12), `test_tanya_kn_f0_time.py` (6), dan `test_registry_ai_collections.py` (1). **19 test lulus**, meliputi konversi satuan, batas waktu WIB/periode pembanding dan registrasi koleksi AI. Hasil [JUnit](integration_repro/existing_unit_tests.xml) dan [log](integration_repro/existing_unit_tests.log) dilampirkan. Ada satu peringatan pytest mengenai assert rewriting anyio yang sudah diimpor; bukan kegagalan test. Harness memakai konfigurasi audit serial terpisah; konfigurasi pytest repository tetap utuh.

Kelulusan ini tidak memverifikasi keseluruhan alur pembelian/penerimaan, timezone semua laporan, atau otorisasi seluruh koleksi AI. Inventaris 268 berkas test pada laporan 18 bukan jumlah berkas yang telah dijalankan. Sebagian berkas yang tidak mengimpor HTTP secara langsung tetap memakai fixture HTTP dari berkas lain; klasifikasi import tidak boleh dianggap bukti bahwa test itu murni.

## IX07 — P1 — Pengaturan Finance entitas lain dapat diubah melalui scope

**Lokasi:** [backend/routers/settings.py:45](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/settings.py#L45) · [backend/services/entity_lifecycle_service.py:452](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_lifecycle_service.py#L452)

**Bukti:** I5-SEC01 dan kontrol I5-C01. User finance U hanya mempunyai allowed_entity_ids=[A], dengan izin entity.update. GET /api/settings/effective?entity_id=B ditolak 403. PUT /api/settings dengan scope=B dan finance.base_currency=USD justru menghasilkan 200; konfigurasi efektif B berubah dari IDR menjadi USD.

**Akar kesalahan:** Route update hanya memeriksa apakah scope adalah entitas yang ada. Ia tidak memanggil resolver akses entitas seperti route baca. Penjaga body generik hanya mengenali entity_id dan owner_entity_id, sehingga nama field scope melewatinya. Keberadaan permission entity.update tidak memberikan user ini akses baca B; hak modul dan hak badan usaha menjadi tidak konsisten.

**Dampak dan batas bukti:** Pengguna berizin mengubah master entitas A dapat memodifikasi parameter Finance, tax, sales, inventory, purchasing atau commission entitas B. Bukti dinamis menguji base_currency; perubahan tiap parameter lain belum diuji satu per satu. Ini tidak berarti pengguna tanpa login bisa mengubah pengaturan, dan tidak membuktikan journal lama dikonversi otomatis.

**Perbaikan:** Resolusi target scope harus memakai kebijakan entitas yang sama untuk baca dan tulis. Pisahkan hak perubahan global dari override entitas. Periksa status entitas dan penugasan aktor sebelum lookup/upsert; audit harus mencatat target B secara benar, bukan hanya konteks header A.

**Kriteria selesai:** User A dengan entity.update tetap mendapatkan 403 saat menulis B; user yang ditugaskan ke B dapat mengubah B sesuai kebijakan. Uji scope global, all, entitas arsip, entitas tidak dikenal, header A/body scope B, dan perubahan melalui UI. Pastikan penolakan tidak meninggalkan perubahan konfigurasi.

## IX08 — P1 — Approval basi dapat menimpa penolakan buka periode dan mengaktifkan izin posting

**Lokasi:** [backend/services/period_unlock_service.py:179](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/period_unlock_service.py#L179) · [backend/services/period_unlock_service.py:208](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/period_unlock_service.py#L208) · [backend/services/gl_service.py:463](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L463)

**Bukti:** I5-FN01, kontrol I5-C02. Permintaan dibuat memakai request_unlock terhadap periode September 2026 yang tertutup. Approval membaca pending lalu ditahan sementara. Rejection lain menyelesaikan penulisan rejected. Approval dilanjutkan dan menulis approved. Record akhir masih membawa rejected_by=Rejector, tetapi enforce_closed_period_guard menerima unlock tersebut. Kontrol terpisah menunjukkan pengusul memang ditolak jika menyetujui permintaannya sendiri.

**Akar kesalahan:** Approve dan reject memeriksa status dari snapshot, lalu update_one hanya memfilter id. Tidak ada conditional write status=pending atau version yang menjamin satu keputusan terminal. Dual control terhadap identitas pengusul tidak menyelesaikan konflik keputusan.

**Dampak dan batas bukti:** Penolakan yang telah selesai dapat dibatalkan oleh request approval yang sebelumnya sudah berjalan. Masa buka periode menjadi aktif dan penjaga GL mengizinkan posting mundur. Test mencapai penjaga GL asli, tetapi tidak membuat jurnal lanjutan dalam skenario ini; jadi bukti langsungnya adalah izin posting, bukan perubahan laporan saldo.

**Perbaikan:** Lakukan compare-and-set atas status pending dan versi, atau conditional find_one_and_update yang mengembalikan satu hasil keputusan. Pihak yang kalah wajib menerima konflik dan tidak membuat audit sukses. Pertahankan riwayat keputusan; jangan menghapus jejak penolakan dengan menormalisasi field secara buta. Tinjau idempotensi approve/reject serta permintaan ganda.

**Kriteria selesai:** Jalankan approve-vs-reject, approve-vs-approve dan retry dengan barrier deterministik serta database nyata. Hanya satu keputusan boleh berhasil. Jika reject menang, find_active_unlock kosong dan guard jurnal harus menolak. Pertahankan kontrol self-approval dan expiry. Tambahkan uji jurnal lengkap serta rekonsiliasi sesudah reversal/periode tertutup.

## IX09 — P2 — Membuka kembali inspeksi tidak membatalkan indikator selesai pada retur

**Lokasi:** [backend/services/inspection_service.py:798](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/inspection_service.py#L798) · [backend/services/inspection_service.py:832](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/inspection_service.py#L832) · [backend/services/return_service.py:580](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/return_service.py#L580) · [frontend/src/features/sales/ReturnJourneyPanel.jsx:190](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/sales/ReturnJourneyPanel.jsx#L190)

**Bukti:** I5-WM02. finish pada dokumen inspeksi terkait retur mengisi sales_returns.inspect_done_at. Setelah reopen, inspeksi kembali in_progress dan finished_at kosong, tetapi inspect_done_at retur tetap berisi waktu penyelesaian lama. UI ReturnJourneyPanel menggunakan field retur ini untuk warna dan waktu milestone selesai. Efek visual ditelusuri dari kode; belum dilihat melalui browser.

**Akar kesalahan:** Sinkronisasi berjalan satu arah pada finish melalui mark_inspected_by_document. Reopen hanya mengubah dokumen inspeksi, tanpa memperbarui proyeksi milestone retur atau menandainya telah dibatalkan. Dua representasi status yang seharusnya konsisten menjadi berbeda.

**Dampak dan batas bukti:** Operator melihat retur sudah selesai diperiksa ketika SPK inspeksi telah dibuka untuk koreksi. Bukti ini tidak menunjukkan otomatis terjadinya settlement atau refund; perluasan ke pelepasan stok/Finance harus diuji terpisah. Riwayat selesai sebelumnya tetap relevan, tetapi tidak boleh disajikan sebagai status aktif saat ini.

**Perbaikan:** Tentukan SSOT status inspeksi dan cara proyeksi ke retur diperbarui pada finish, reopen, cancel dan pergantian dokumen aktif. Pertahankan history selesai sebelumnya dengan event pembatalan. Jika beberapa inspeksi dapat terkait ke satu retur, jangan mengosongkan milestone secara buta; hitung dari dokumen aktif yang menjadi dasar keputusan.

**Kriteria selesai:** Finish → reopen mengubah milestone aktif retur menjadi belum selesai; history menyimpan keputusan sebelumnya. Finish ulang mengisi timestamp/versi baru. Uji beberapa SPK, retry sinkronisasi, kegagalan update retur, dan rendering ReturnJourneyPanel tanpa perlu refresh manual yang menyesatkan.

## IX10 — P1 — Baca dan keputusan buka periode tidak memeriksa penugasan entitas

**Lokasi:** [backend/routers/period_unlocks.py:42](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/period_unlocks.py#L42) · [backend/routers/period_unlocks.py:75](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/period_unlocks.py#L75) · [backend/routers/period_unlocks.py:88](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/period_unlocks.py#L88) · [backend/services/period_unlock_service.py:179](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/period_unlock_service.py#L179)

**Bukti:** I5-SEC02/SEC03 dan kontrol I5-C03. User U hanya ditugaskan ke A dan diberi period.unlock. POST membuat usul untuk B ditolak 403, tetapi GET list dengan entity_id=B mengembalikan usul sintetis B (200); POST /finance/period-unlocks/FOREIGN/approve mengubahnya menjadi approved (200). Pengusul usul B berbeda dari U sehingga kontrol dua orang tetap lolos.

**Akar kesalahan:** Create memanggil _resolve_entity. List dan active hanya memanggil current_user lalu meneruskan entity_id tanpa resolver; approve/reject mencari record berdasarkan id dan memanggil service tanpa memeriksa pemilik entitas. Validasi body tidak menolong karena approve tidak membawa entity_id.

**Dampak dan batas bukti:** Aktor berizin modul pada A dapat mengotorisasi pembukaan buku B. Data alasan dan status permintaan B juga terbaca. Uji dinamis membuktikan list dan approve; reject dan active mempunyai pola yang sama secara statis, belum masing-masing diuji dinamis. Ini bukan bypass login atau penghapusan kebutuhan period.unlock.

**Perbaikan:** Resolve scope daftar dari konteks pengguna dan validasi semua query override. Untuk approve/reject, load resource lalu wajibkan akses write terhadap entity_id pemilik sebelum perubahan; jangan percaya header sebagai pemilik resource. Terapkan kontrak sama pada active dan batch reclose dengan membedakan operasi scheduler internal dari operasi user.

**Kriteria selesai:** User A tidak dapat list/active/read/approve/reject milik B walaupun tahu ID dan memiliki period.unlock. User yang sah pada B tetap dapat memutuskan dengan dual control. Uji header A/query B, tanpa query, all, entitas arsip, dan request langsung tanpa UI. Tidak ada record maupun audit sukses yang berubah saat ditolak.

## PG01 — Gap kebijakan: inspeksi dapat selesai setelah baru sebagian baris diperiksa

I5-WM01 menghasilkan `status=done`, keputusan `terima`, `summary.inspected=1`, dan `summary.lines=2`. Syarat pada `inspection_service.finish` baris 814 memakai `any(inspected_at)`, sehingga cukup satu baris telah diperiksa. UI menunjukkan jumlah yang diperiksa, tetapi tombol Tutup SPK pada `InspectionDetailPanel.jsx:355` hanya memeriksa busy dan pilihan keputusan.

**Ini belum diklasifikasikan sebagai cacat universal:** bisnis mungkin sengaja mengizinkan sampling. Namun kode yang diuji tidak mewajibkan deklarasi sampling plan, ukuran sampel, representativitas lot atau alasan pengecualian. Jika seluruh baris adalah unit pemeriksaan wajib, guard semestinya memerlukan semuanya selesai. Jika sampling dibolehkan, tampilkan kebijakan, cakupan hasil dan unit yang belum diperiksa; hindari keputusan keseluruhan yang seolah-olah setiap roll sudah diperiksa. Uji juga hold dan rejection per baris sebelum pelepasan stok. Skema uji memakai dua baris sintetis dan tidak menjalankan inspeksi fisik atau grading setiap roll.

## Gambaran masalah lintas flow

IX07 dan IX10 menunjukkan celah yang lebih luas daripada satu endpoint: pembatasan badan usaha terpasang pada sebagian langkah flow, tetapi tidak konsisten pada seluruh resource/action. Memperbaiki nama field body saja tidak melindungi keputusan berbasis ID. Audit akses harus menelusuri create → list → detail → approve/reject → effect, dengan pemilik dokumen menjadi dasar setiap langkah.

IX08 menunjukkan bahwa kontrol dua orang memerlukan identitas **dan** transisi yang atomik. Dua reviewer yang sah tetap dapat menghasilkan keputusan bertentangan. IX09 menunjukkan masalah SSOT pada perubahan balik: proyeksi yang benar ketika finish dapat salah setelah reopen. Karena itu uji happy path saja tidak cukup untuk menyatakan Finance/WMS benar.

Total paket integrasi putaran 4 dan 5 sekarang memuat **28 skenario** (11 + 8 + 9), terpisah dari 19 test bawaan dan probe autentikasi 1.353 endpoint. Angka ini bukan persentase cakupan seluruh flow. Trace di laporan 21 tetap snapshot putaran 4; tambahan putaran 5 tidak diam-diam dimasukkan ke angka tersebut.

## Sisa pekerjaan dan status kelayakan

Belum layak memberi pernyataan bahwa semua kode/flow telah teruji atau Finance telah akurat sepenuhnya. Masih terbuka UAT browser seluruh fitur, dataset transaksi acuan sampai laporan akhir, role/state matrix, crash recovery worker, deployment bootstrap/index, dan RFID/gate nyata. Temuan baru memperkuat perlunya perbaikan isolasi entitas, transisi atomik dan proyeksi status sebelum sign-off.

Perbandingan enterprise RFID/WMS yang sudah disertai sumber primer tetap di [10 — blueprint enterprise](10_BLUEPRINT_RFID_WMS_ENTERPRISE.md). Jika nama tautan berbeda pada direktori keluaran, gunakan daftar dokumen pada laporan 07. Tambahan ini tidak mengklaim benchmark hardware atau UAT vendor baru.
