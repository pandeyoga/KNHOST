# Brief review audit UI tahap 2 (ERP Kain Nusantara)

Anda me-review **tangkapan layar JPEG** hasil crawler otomatis: setiap layar, tab di dalam halaman, halaman detail,
pop-up (form buat & **ubah**, konfirmasi, pilih), pop-up bersarang, menu, dan perubahan inline — desktop 1440 px,
responsif 390 px (`mobile`), dan aplikasi HP khusus peran (`hpapp`). Data dari DB uji (banyak nama "TEST"/"QA" — itu
data uji, **bukan** temuan).

Acuan "benar" dan format laporan: baca dulu `ui_review_rubric.md` (folder yang sama dengan folder `crawl`). Patuhi
format keluarannya, dengan perubahan berikut:

* Id keadaan = `<view> #<n> <kind>` (n & kind tertulis di paket). Sebut **jalur klik** (path) untuk pop-up/detail
  supaya bisa dibuka ulang.
* Crawler **memblokir semua penyimpanan**. Pesan "Network Error"/"Gagal …" yang muncul SETELAH tombol aksi
  (Simpan/Setujui/Kirim…) adalah akibat audit, **bukan temuan**. Kotak konfirmasi BAWAAN PERAMBAN (`confirm`/`alert`)
  dicatat di kolom `native` — itu **temuan** (harus pop-up aplikasi).
* Fokus tahap 2 = yang belum pernah diaudit: **pop-up & form** (judul, label, penanda wajib, urutan isian, lebar,
  kaki tombol, form edit vs form buat konsisten), **dialog konfirmasi/alasan**, **halaman detail** & tab-nya, **tab di
  dalam halaman**, menu tindakan, dan tampilan HP. Halaman daftar yang sudah disapu kemarin cukup dicek sekilas.
* Penanda otomatis di paket (`[T]/[S]/[R] …`) adalah petunjuk, bukan kesimpulan — konfirmasi di gambar; buang yang
  keliru (mis. "kode-mentah" pada alamat email/slug yang wajar).
* Untuk setiap temuan sebut **komponen/berkas yang kemungkinan** (bila tahu dari judul/testid) — tidak wajib.
* Pop-up yang tampil sama di banyak tempat cukup dilaporkan sekali (sebut di mana saja muncul).
* Sesi crawler kini sama dengan login normal: entitas aktif **Sukacita** (admin) / entitas rumah peran lain. Bila sebuah
  tangkapan masih menunjukkan kepala "Badan usaha", spinner, skeleton, atau "Memuat…", masukkan ke daftar **"Perlu tangkap
  ulang"** (bukan temuan) — kecuali keadaan itu bertahan (mis. galat izin, "Tidak ada hasil" pada daftar yang jelas
  ada datanya di layar lain).
* Jangan mengedit berkas apa pun. Tulis laporan ke berkas keluaran yang disebut di tugas Anda.
