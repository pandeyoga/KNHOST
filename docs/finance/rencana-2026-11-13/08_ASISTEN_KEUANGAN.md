# Rancangan — Asisten Keuangan (AI)

Status: rancangan untuk diputuskan pemilik. Belum ada kode. KNHOST dibaca di `9834947`; DAHOST (proyek ERP lain milik
pemilik) dibaca di `3bc1520` sebagai contoh. Butir bertanda ✔ dicek langsung pada berkas:baris yang disebut.

## 0. Ringkasan

- **Yang diminta:** asisten yang paham keuangan — menjawab pertanyaan, menganalisis, membuat laporan, dan **menginput
  langsung**: jurnal, cek jurnal, catat pembayaran piutang dan hutang.
- **KNHOST sudah punya separuhnya.** "Tanya KN" kuat di sisi baca (sembilan alat, pemeriksa angka, kuota biaya, laporan
  terjadwal), tetapi sisi tulisnya hanya tiga jenis non-keuangan, dan jurnal, buku besar, neraca, rekonsiliasi, status
  periode, antar-PT belum terbuka untuknya.
- **DAHOST punya separuh lainnya.** Kekuatannya bukan pada modelnya, melainkan pada satu keputusan rancangan: asisten
  **memanggil pintu yang sama dengan tombol di layar**, memakai sesi pengguna. Izin, penjaga entitas, kunci periode
  berlaku persis seperti di layar. Ditambah kartu tindakan: rencana lama→baru, alasan, ketik ulang nominal, persetujuan
  orang kedua, sekali jalan, gagal tidak kembali ke antre.
- **Usulan:** pertahankan mesin baca KNHOST, ambil pola tulis DAHOST. Asisten **tidak** diberi jalan sendiri ke
  database untuk menulis.
- **Batas yang jujur:** asisten hanya seaman pintu yang dipanggilnya. Hari ini sebagian besar pintu uang KNHOST belum
  aman untuk diulang (tanpa kunci idempotensi, entitas dari isi permintaan, jurnal gagal tanpa penanda). Karena itu
  kemampuan tulis dibuka **bertahap mengikuti paket fondasi**; yang bisa segera dibuka adalah baca keuangan dan catat
  kwitansi piutang.

## 1. Dua sistem yang ada

| Kemampuan | KNHOST ("Tanya KN") | DAHOST (asisten AI) |
|---|---|---|
| Penyedia model | OpenAI (Responses API); model dari konfigurasi `ai.model_main`; bawaan fitur **mati** | Anthropic; model ditulis di kode |
| Alat baca | 9 alat di atas katalog metrik; membaca MongoDB langsung dengan cakupan buatan sendiri | Alat khusus + semua bacaan layar, lewat endpoint aplikasi |
| Pemeriksa angka | Ada: tiap angka jawaban dicocokkan dengan hasil alat (`services/ai_number_check.py`) — di chat hanya ditempel sesudah jawaban | Tidak ada |
| Laporan | Templat, Excel, jadwal harian/mingguan | PDF/Excel berkop, ringkasan pagi |
| Alat tulis | 3 jenis: draf PO, tindak lanjut penagihan, tindak lanjut pelanggan ✔ `services/ai_actions.py:19` | Katalog ±1.000 aksi layar termasuk jurnal dan pembayaran, bergolongan risiko |
| Cara menulis | Memanggil fungsi layanan langsung, mengulang cek izin secara manual | Memanggil endpoint aplikasi sendiri di dalam proses dengan token pengguna ✔ `core/asisten_ai/alat_base.py:629-660`; konteks baca menolak metode tulis |
| Konfirmasi | Setujui/Abaikan; hanya jumlah yang bisa diubah | Rencana lama→baru; alasan; risiko tinggi: ketik ulang nominal ✔ `core/asisten_ai/tindakan.py:691-702`; di atas batas: persetujuan orang kedua |
| Bila gagal | Status kembali `pending` ✔ `ai_actions.py:208-210` | Berakhir `gagal`; kartu kedaluwarsa 24 jam |
| Yang dilarang lewat asisten | — | Tutup/kunci/buka periode, tutup tahun, pengguna dan peran, cadangan, hapus akun ✔ `core/asisten_ai/katalog_aksi/aturan.py:82-116` |
| Privasi | Nama pelanggan/supplier dan nominal dikirim apa adanya | Nama diganti kode, data gaji dibuang, kontak disamarkan (`services/ai/privacy.py`) |
| Kunci API | Terenkripsi bila kunci rahasia terpasang | Tersimpan polos |
| Biaya | Anggaran bulanan + kuota harian per pengguna | Harian/bulanan/per fitur + sakelar per akun |
| Uji | ±84 tes + 120 pertanyaan evaluasi | ±470 tes + klien model tiruan |

Yang bisa dipindahkan dari DAHOST tanpa terikat penyedia: pola kartu (siapkan → jalankan → batalkan), pola "panggil
pintu sendiri", golongan risiko dan daftar larangan, penyamaran data, pemeriksaan "data masih sama dengan saat kartu
dibuat", dan pola klien tiruan untuk tes. Yang tidak bisa dipindahkan begitu saja: mesin percakapannya (terikat satu
penyedia) dan katalog aksinya (khusus rute DAHOST).

## 2. Temuan tambahan pada asisten yang ada

| ID | Tingkat | Temuan | Bukti | Ditutup oleh |
|---|---|---|---|---|
| AG-01 ✔ | Sedang | Konfirmasi yang gagal mengembalikan kartu ke `pending`, padahal PO dibuat satu per satu — mengulang bisa menggandakan PO yang sudah jadi (belum diuji jalan) | `services/ai_actions.py:160-173, 208-210` | AG-T1 |
| AG-02 | Sedang | Draf tanpa masa berlaku; entitas tidak diperiksa ulang saat disetujui | `ai_actions.py:127, 199-214` | AG-T1 |
| AG-03 | Sedang | Alat membaca database dengan aturan cakupan sendiri, terpisah dari izin di router — dua tempat aturan yang bisa menyimpang (mewarisi kelas IA-02) | `services/analytics_engine.py:34-72` | AG-T2 |
| AG-04 | Sedang | Pencarian supplier, gudang, dan sales oleh asisten tanpa saringan entitas | `services/ai_tools.py:364-366` | AG-T1 |
| AG-05 | Rendah | Skema alat menawarkan jenis dokumen dan ringkasan yang tidak dilayani server | `ai_tools.py:354-355, 397-401` | AG-T1 |
| AG-06 | Keputusan | Nama pihak dan nominal dikirim ke penyedia model tanpa penyamaran | `services/ai_chat_service.py:96-98, 296` | K-43 |

Dan dari audit: "pendapatan diakui" yang dijawab Tanya KN ikut menghitung jurnal penutup (RP-04, ditutup PK-16).

## 3. Prinsip rancangan

1. **Satu pintu.** Asisten memanggil endpoint yang sama dengan layar, dengan sesi pengguna yang sedang bertanya dan
   header entitas aktifnya. Tidak ada jalur tulis khusus asisten. Akibatnya setiap perbaikan fondasi otomatis
   melindungi asisten, dan asisten tidak pernah bisa melakukan yang tidak bisa dilakukan penggunanya.
2. **Baca dan tulis dipisah.** Percakapan berjalan dalam konteks baca. Tulis hanya terjadi saat pengguna menyetujui
   sebuah **kartu tindakan**, di luar giliran model.
3. **Model mengusulkan; kode yang menghitung dan menjalankan.** Angka di jawaban berasal dari hasil alat. Total,
   selisih, dan persen dihitung kode. Model tidak menjumlah.
4. **Isi dokumen adalah data, bukan perintah.** Keterangan jurnal, catatan pelanggan, teks hasil baca lampiran tidak
   pernah menjadi alasan memanggil alat tindakan.
5. **Setiap tindakan bisa dijelaskan sesudahnya:** siapa meminta, apa rencananya, apa yang disetujui, siapa penyetuju
   kedua, apa hasilnya, dan dokumen apa yang lahir.
6. **Lebih baik menolak daripada menebak.** Bila pelanggan, faktur, atau rekening yang dimaksud tidak tunggal, asisten
   bertanya.

## 4. Kemampuan

### 4.1 Tanya dan periksa (baca)

| Alat baca baru | Pintu yang dipanggil | Catatan yang ikut ditampilkan |
|---|---|---|
| Cari dan buka jurnal; buku besar per akun; neraca saldo | `routers/gl.py` | Entitas dan periode |
| Laba-Rugi, Neraca, Arus Kas, Perubahan Ekuitas | `routers/financial_statements.py` | Mode gabungan: "belum dieliminasi" (RC-01) |
| Umur piutang dan hutang; kartu pelanggan/supplier | `routers/ar_aging.py`, `vendor_bills.py` | Dasar jatuh tempo yang dipakai (RP-03, RP-07) |
| Posisi kas dan bank; mutasi belum cocok; saran pencocokan | `routers/bank*.py` | — |
| Status periode; daftar posting gagal | `routers/closing.py`, `posting_failures.py` | Jenis dokumen yang belum tercakup panel (sampai PK-18) |
| Saldo antar-PT; kandidat eliminasi | `routers/interco.py`, `consolidation.py` | — |
| Faktur pajak dan rekap PPN | `routers/tax_*.py` | — |
| Anggaran vs realisasi | `routers/budgets.py` | — |

Contoh yang harus bisa dijawab dengan sumber yang bisa diklik: "kenapa laba Oktober turun dibanding September?",
"jurnal mana saja yang menyentuh akun 2-1100 minggu ini?", "faktur supplier mana yang jatuh tempo sampai Jumat?",
"apakah ada kas tanpa jurnal bulan ini?", "pelanggan mana yang lewat plafon?".

Setiap jawaban keuangan memuat: PT, periode atau "per tanggal", dan tautan ke layar sumbernya. Pemeriksa angka yang
sudah ada dijadikan **penghalang** untuk jawaban keuangan: bila ada angka di jawaban yang tidak ditemukan di hasil alat,
jawaban tidak dikirim dan asisten mengulang atau menyatakan tidak bisa.

### 4.2 Analisis dan laporan

- **Paket tutup buku bulanan** (Excel/PDF, per PT): Laba-Rugi, Neraca, Arus Kas, umur piutang dan hutang, daftar
  pencocokan (akun kontrol vs buku pembantu, saldo antar-PT dua sisi, kas vs buku besar), posting gagal, jurnal manual
  bulan itu. Angka dari server; model hanya menulis ringkasan yang lolos pemeriksa angka.
- **Ringkasan pagi keuangan** (terjadwal, tanpa alat tindakan): jatuh tempo hari ini, uang masuk belum terverifikasi
  bank, posting gagal, pelanggan baru melewati plafon, selisih rekonsiliasi.
- **Analisis perubahan** (alat `analyze_change` yang ada) diperluas ke akun buku besar.

### 4.3 Input lewat kartu tindakan (tulis)

Alur satu tindakan — contoh "catat pembayaran pelanggan Toko Maju 5 juta ke BCA":

```text
1. Asisten mencari pelanggan dan tagihan terbuka (baca). Bila tidak tunggal → bertanya.
2. SIAPKAN  (hanya baca): menyusun rencana —
      PT, pelanggan, nominal, rekening, tanggal, alokasi per tagihan,
      nilai sebelum → sesudah (sisa piutang), jurnal yang AKAN terbit,
      dan sidik data (sisa tagihan saat ini).
   Kartu tersimpan berstatus MENUNGGU. Giliran model berhenti di sini.
3. Pengguna membaca kartu, boleh mengubah isian yang diizinkan, lalu menyetujui:
      risiko sedang → alasan singkat;  risiko tinggi → alasan + ketik ulang nominal.
4. Bila nominal di atas batas → menunggu PENYETUJU KEDUA (bukan pembuat).
5. JALANKAN sekali: sidik data dibandingkan; bila data sudah berubah → kartu ditolak, minta disiapkan ulang.
      Panggil endpoint yang sama dengan layar, dengan kunci idempotensi = id kartu.
6. Hasil: BERHASIL (tautan ke dokumen dan jurnalnya) atau GAGAL (pesan galat asli). Tidak pernah kembali MENUNGGU.
7. Kartu kedaluwarsa setelah 24 jam atau bila pengguna mengirim permintaan baru yang menggantikannya.
```

Tahapan pembukaan kemampuan tulis mengikuti kesiapan pintunya:

| Golongan | Tindakan | Pintu | Siap setelah | Konfirmasi |
|---|---|---|---|---|
| A — tanpa akibat uang | Catat tindak lanjut penagihan; janji bayar; lampirkan bukti; buat pengingat | sudah ada | AG-T1 | Setujui |
| B — uang masuk | **Catat kwitansi piutang** (termasuk alokasi) | `routers/ar_receipts.py` — paling siap: sudah ber-idempotensi, entitas diadu, periode diperiksa dulu, ada `gl_status` | AG-T3; lebih baik setelah PK-19 | Alasan + ketik ulang nominal |
| B — pencocokan | Cocokkan mutasi bank dengan kwitansi; alokasi titipan | `routers/bank_reconciliation.py` | PK-15, PK-21 | Setujui |
| B — perbaikan | Ulang posting yang gagal | `routers/posting_failures.py` | PK-18 | Setujui |
| C — uang keluar | Bayar tagihan supplier / kontrabon | layanan bayar hutang | **PK-05**, PK-12 | Alasan + ketik ulang + penyetuju kedua di atas batas |
| C — kas | Kas manual (biaya, setoran) | `routers/cash.py` | PK-09, PK-12, PK-20 | Sama |
| C — jurnal | **Jurnal manual**; balik jurnal | `routers/gl.py` | PK-09, PK-10, PK-12, **PK-36** | Selalu penyetuju kedua (K-04) |
| Dilarang | Tutup/buka periode; ubah bagan akun dan pemetaan; true-up persediaan; ubah plafon; bebaskan denda; eliminasi konsolidasi; pengguna dan izin; pengaturan asisten sendiri; hapus apa pun | — | — | Hanya di layar |

Untuk jurnal manual ada tahap antara yang bisa dibuka lebih awal: asisten menyusun **draf jurnal** (akun, debit,
kredit, keterangan, lampiran) yang muncul di layar Jurnal untuk diperiksa dan diposting manusia. Ini memerlukan status
"draf" yang sungguh dipakai di jurnal manual — sekarang jurnal manual langsung terposting (GL-06).

Input dari berkas: pengguna mengunggah bukti transfer, faktur supplier, atau rekening koran; isi dibaca (mesin baca
dokumen yang sudah ada di KNHOST), lalu asisten menyiapkan kartu dengan lampiran itu. Teks hasil baca diperlakukan
sebagai data (prinsip 4).

## 5. Pengaman

| Risiko | Pengaman |
|---|---|
| Asisten mengulang panggilan (batas waktu, coba lagi) | Kunci idempotensi = id kartu; pintu tujuan wajib ada di daftar idempotensi (aturan E6 di `04`) |
| Model mengisi entitas atau id sembarang | Entitas dari sesi; pintu memakai `resolve_requested_entity` (aturan E1); id diadu di server |
| Satu orang membuat dan menyetujui | Penyetuju kedua untuk golongan C; pembuat tidak bisa menyetujui kartunya sendiri pada tahap kedua |
| Data berubah di antara siapkan dan jalankan | Sidik data dibandingkan sebelum jalan |
| Kartu lama disetujui belakangan | Kedaluwarsa 24 jam; satu kartu aktif per percakapan |
| Jurnal gagal tetapi dilaporkan berhasil | Asisten melaporkan `gl_status` dokumen, bukan sekadar kode 200 (perlu PK-18) |
| Angka laporan yang salah diulang dengan yakin | Label catatan pada alat baca; RP-04, RC-01 diperbaiki dulu (PK-16) |
| Perintah terselip di keterangan atau lampiran | Aturan di instruksi sistem; alat tindakan tidak tersedia pada giliran yang baru saja membaca teks pihak luar tanpa permintaan pengguna |
| Data pribadi dan rahasia dagang ke penyedia | Penyamaran nama (kode pengganti) dan pembuangan data gaji sebelum dikirim; pilihan per PT (K-43) |
| Biaya tak terkendali | Anggaran dan kuota yang ada; batas jumlah tindakan per hari per pengguna |
| Salah guna hak | Fitur per akun bawaan mati; golongan B dan C dinyalakan per orang oleh pemilik |
| Tidak bisa diaudit | Koleksi kartu menyimpan permintaan, rencana, perubahan oleh pengguna, penyetuju, hasil, dan id dokumen; dokumen hasil menandai "lewat asisten" beserta id kartunya |

## 6. Letak di layar

- Tidak ada menu baru. Asisten tetap di **Tanya KN**, dengan dua tambahan: mode "Keuangan" (alat baca keuangan aktif)
  dan tab **Tindakan** (semua kartu: menunggu saya, menunggu orang lain, selesai, gagal).
- Tombol "Tanya soal layar ini" di layar keuangan membuka panel samping dengan konteks layar (PT, periode, dokumen yang
  sedang dibuka).
- Kartu yang menunggu penyetuju kedua juga muncul di Pusat Persetujuan.

## 7. Penyedia model

Rancangan ini tidak bergantung pada penyedia tertentu. Pilihannya (K-43):

| Pilihan | Untuk | Lawan |
|---|---|---|
| Tetap memakai integrasi yang sudah ada di KNHOST | Tidak ada pekerjaan pindah; pemeriksa angka, kuota, dan evaluasi sudah terpasang | Pola kartu DAHOST harus ditulis ulang di atasnya (tetap bisa: polanya netral) |
| Memindahkan mesin percakapan DAHOST | Sudah menangani banyak kasus tepi percakapan panjang | Terikat satu penyedia dan satu versi pustaka; katalog aksinya tidak bisa dipakai; dua mesin harus dirawat sampai yang lama dipensiunkan |
| Lapisan tipis penyedia (satu antarmuka, dua pelaksana) | Bebas berganti; tes memakai pelaksana tiruan | Sedikit pekerjaan tambahan di awal |

Usulan saya: lapisan tipis penyedia + pertahankan mesin KNHOST untuk baca + tulis ulang pola kartu DAHOST di KNHOST.
Yang menentukan mutu asisten keuangan adalah alat dan pengamannya, bukan perpindahan mesin.

## 8. Tahap bangun

| Tahap | Isi | Prasyarat | Selesai bila |
|---|---|---|---|
| AG-T1 Rapikan yang ada | AG-01, 02, 04, 05; kartu: gagal = gagal, masa berlaku, entitas diperiksa ulang; lapisan penyedia + pelaksana tiruan untuk tes | — | Konfirmasi yang gagal di tengah tidak bisa menggandakan PO; kartu kedaluwarsa ditolak |
| AG-T2 Baca keuangan | Pemanggil "pintu sendiri" (dalam proses, sesi pengguna, konteks baca menolak tulis); alat baca §4.1 dengan catatan; pemeriksa angka sebagai penghalang; penyamaran data sesuai K-43 | PK-09, PK-16, PK-17 | Pengguna PT-A tidak bisa memperoleh angka PT-B lewat asisten dengan cara apa pun; 60 pertanyaan keuangan evaluasi lulus dengan angka = hasil layar |
| AG-T3 Kartu golongan A dan B | Mesin kartu (siapkan/jalankan, sidik, idempotensi, kedaluwarsa, jejak); tindak lanjut, kwitansi piutang, pencocokan bank, ulang posting | AG-T2; PK-15, PK-18, PK-21 sesuai tindakannya | Dua persetujuan bersamaan atas satu kartu → satu kwitansi; data berubah → kartu ditolak; dokumen hasil memuat id kartu |
| AG-T4 Laporan | Paket tutup buku; ringkasan pagi | AG-T2; PK-18 | Paket satu bulan = angka layar, ditandatangani pemeriksa angka |
| AG-T5 Kartu golongan C | Bayar supplier, kas manual, draf jurnal → jurnal manual; penyetuju kedua; batas nominal | PK-05, PK-10, PK-12, PK-20, PK-36; K-44 | Kartu di atas batas tidak jalan tanpa penyetuju kedua; jurnal ke akun kontrol ditolak oleh pintunya |

Evaluasi yang harus ada sebelum tiap tahap dinyalakan: kumpulan pertanyaan dengan jawaban yang sudah diverifikasi
(memperluas 120 pertanyaan yang ada), tes tindakan (ganda, kedaluwarsa, salah entitas, data berubah), dan tes sisipan
perintah pada keterangan jurnal dan lampiran.

## 9. Yang tidak dijanjikan

- Asisten tidak membuat pembukuan benar bila pintu di bawahnya salah. Ia mempercepat pekerjaan orang yang berwenang,
  dengan jejak yang lebih rapi daripada klik biasa.
- Angka "akurasi" yang diiklankan produk sejenis berasal dari penyedianya sendiri; saya tidak menemukan bukti independen.
  Ukuran yang dipakai di sini adalah evaluasi di data acuan KNHOST.
- Otonomi penuh (asisten memposting tanpa persetujuan) tidak dirancang.
