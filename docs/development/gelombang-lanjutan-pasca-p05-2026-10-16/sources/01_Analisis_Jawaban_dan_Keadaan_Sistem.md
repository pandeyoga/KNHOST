# Analisis Jawaban Pemilik dan Keadaan Sistem

**Project:** ERP Kain Nussantara  
**Produksi IT:** PT Kubus Teknologi Indonesia  
**Tanggal:** 16 Oktober 2026  
**Acuan kode:** main `64d81f29577dae4daa86ddc64689dec7243804f2`, commit 14 Oktober, “P05 ditutup: DEC-13 retur bahan MKO batal, resep acuan ACC-33, perbaikan pembulatan”.

Dokumen ini memproses seluruh jawaban terbaru nomor 1–11, termasuk 11.b dan 11.c. Aturan yang telah dijawab dibedakan dari kemampuan kode yang terbukti serta usulan yang perlu ditinjau. Tidak ada perubahan source atau konfigurasi ERP. Domain retur tetap ditahan; penyebutan retur di QC hanya mencatat sumber roll yang diminta.

Pemeriksaan ini terarah pada jawaban terbaru dan rantai proses terkait, bukan klaim seluruh ERP telah diuji ulang. Kode dibaca pada snapshot terbaru; lima pemeriksaan fungsi asli dijalankan secara terisolasi tanpa database/perangkat/live ERP. Hasil pemeriksaan perangkat dan transaksi produksi belum tersedia.

## Ringkasan status

| Jawaban | Pemahaman yang dicatat | Status kebutuhan / keadaan sekarang |
|---|---|---|
| 1 | Desain existing yang sudah ACC tetap masuk proofing; desain untuk Special Order diberi label yang dapat difilter | Jelas; fondasi design→proofing ada, pemilihan existing dan filter tujuan perlu diselaraskan |
| 2 | Alokasi menjadi A memakai harga A; Admin Sales boleh mengajukan harga khusus lagi | Jelas; pengajuan dan amandemen harga ada, tetapi batas tahap serta referensi grade/roll perlu diselaraskan |
| 3 | MD Quality bersumber receiving; bebas memilih roll yang dipotong | Jelas; urutan tagging dan pencatatan pemakaian direkomendasikan di bawah |
| 4 | QC sebelum kirim dapat seluruh roll atau sampling; checkout default tidak meminta QC | Jelas; antrean inspeksi ada, alur permintaan QC SO belum sama dengan random check |
| 5 | Form inspect disesuaikan dengan artikel, customer header, dua warna, roll ID dan tanggal periksa | Jelas; struktur interval/detail cacat belum setara form yang diminta |
| 6 | Sepuluh interval × 15 yard = 150 yard per tampilan; formula belum diberikan | Layout jelas; formula dan contoh hitung tetap menunggu client |
| 7 | Kemungkinan LOT supplier dan nama LOT KN terpisah | Belum diputuskan client; fondasi penyimpanan dua kode sudah ada |
| 8 | Banyak gudang dalam satu lokasi, konsolidasi transit, satu perjalanan banyak SO, Jakarta transit dan SJ berikutnya | Arah bisnis jelas; rancangan dokumen dan dampak status/finance perlu diselaraskan |
| 9 | Kekurangan/kerusakan diselesaikan per kasus; SO diamandemen bila transaksi final berubah | Jelas; transfer aktual dan exception tersedia, penutupan komersial harus mengikuti keputusan nyata |
| 10 | Cutoff pembayaran antar-entitas belum tersedia | Pertanyaan client disiapkan; tidak dibuat tanggal asumsi |
| 11.a | Seluruh data bisnis sesuai hak akses, custom periode, filter dan pilihan kolom | Jelas; export per modul/analitik ada, belum bukti builder seluruh data terpenuhi |
| 11.b | Nilai design berarti skor desain | Jelas; skor desain telah ada dan harus dibedakan dari nilai uang |
| 11.c | Join hanya data terkait yang berguna; rapor designer dan Sales lengkap beserta ringkasan | Jelas; bentuk hasil dan contoh rinci disusun sebagai usulan untuk ditinjau |

## 1. Special Order: desain existing tetap harus proofing

**Jawaban Anda:** “tetap profing saja jadi tetap dibedakan, untuk design spesial order ingat buatkan label pembeda yang bisa di filter”.

Interpretasinya: memakai artwork existing yang sudah ACC menghindari pekerjaan desain ulang yang tidak diperlukan. Persetujuan artwork tetap berbeda dari persetujuan hasil proofing di kain. Artwork ACC tidak boleh membuat Special Order langsung dianggap lolos proofing dan masuk produksi.

Alur yang dicatat:

1. Sales membuat Special Order dan mengisi keinginan customer.
2. Pilih referensi artwork yang sudah memenuhi status desain, atau jalankan pembuatan/redesign bila memang diperlukan. Desain hold tetap menunggu release PIC Designer.
3. Untuk artwork existing yang sudah ACC dan tidak berubah, lanjut ke proofing dengan referensi desain dan versi yang dipakai.
4. Hasil proofing diajukan ke customer melalui Sales.
5. Jika customer meminta perbaikan proofing pada artwork yang sama, lakukan reproofing; riwayat percobaan tetap tersimpan. Perubahan motif mengikuti arahan sebelumnya: Special Order baru.
6. Produksi mengikuti persetujuan hasil proofing dan tahapan finalisasi existing.

**Keadaan sekarang:** callback ACC design sudah membuat permintaan proofing yang terkait OD; keputusan customer dan pembuatan sample revisi juga tersedia. Jadi tidak perlu membuat ulang seluruh flow designer/proofing. Form intake yang dibaca belum menunjukkan pemilih existing artwork ACC/hold yang lengkap seperti kebutuhan Anda; keberadaan `template_id` tidak sama dengan pemilih artwork. [E01: backend/services/special_order_phase2.py:504](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/special_order_phase2.py#L504); [E02: backend/services/special_order_phase2.py:81](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/special_order_phase2.py#L81); [E03: backend/services/design_studio_service.py:469](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/design_studio_service.py#L469); [E04: frontend/src/features/sales/CreateSpecialOrderForm.jsx:31](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/frontend/src/features/sales/CreateSpecialOrderForm.jsx#L31).

**Label dan filter:** tujuan **Internal / Special Order** sebaiknya diturunkan dari hubungan permintaan desain dengan OD. Label **Redesign** menjadi jenis pekerjaan tambahan, bukan pengganti status ACC/hold. Satu desain existing dapat digunakan oleh beberapa pesanan; jangan mengganti tujuan asli desain sampai riwayat penggunaan internalnya hilang. Daftar penggunaan desain dapat menunjukkan semua OD terkait. Ini usulan representasi untuk memenuhi filter, bukan keputusan menambah flow persetujuan baru.

Checklist print paper tetap aktivitas designer pada round yang bersangkutan. ACC PIC tetap persetujuan internal desain; ACC customer dicatat Sales pada tahap yang sesuai. Tidak ditambahkan kewajiban kedua PIC harus menyetujui.

## 2. Grade A dan pengajuan ulang harga khusus

**Jawaban Anda:** “menjadi harga grade A namun bisa diminta special price baru lagi ... jika terjadi pergantian alokasi grade oleh admin sales maka admin sales bisa mengajukan harga special price lagi/harga khusus”.

Aturannya jelas: harga acuan mengikuti grade hasil alokasi, lalu harga khusus menjadi pengecualian yang diajukan melalui mekanisme approval existing. Harga khusus lama tidak boleh diasumsikan otomatis berlaku untuk alokasi/qty/grade baru yang berbeda tanpa kecocokan lingkup persetujuan.

Contoh: awalnya roll B, kemudian Admin Sales memilih roll A. Sistem memperlihatkan qty final roll A dan harga acuan A. Admin Sales dapat menerapkan harga acuan tersebut atau mengajukan harga khusus untuk kondisi baru. Harga yang belum disetujui belum menjadi nilai final transaksi.

**Keadaan sekarang:** pengajuan harga khusus per SO tersedia, tetapi endpoint tersebut membatasi status ke draft/reserved/waiting_approval/waiting_stock; SO `confirmed` ditolak. Override Admin Sales mempunyai jalur **amandemen harga** tersendiri. Keduanya harus dipakai sesuai tahap, bukan membuat fitur approval paralel yang bertentangan. [E06: backend/routers/so_approvals.py:89](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/routers/so_approvals.py#L89); [E07: backend/services/so_override_service.py:316](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/so_override_service.py#L316).

**Implikasi penting:** kalimat “boleh mengajukan lagi” tidak berarti endpoint lama sudah menerima semua tahap SO. Pada tahap sebelum persetujuan gunakan pengajuan harga khusus; sesudah tahap tersebut dan sebelum aktivitas gudang terkunci gunakan amandemen harga yang sudah tersedia sesuai hak akses. Tampilan sebaiknya memakai bahasa bisnis yang konsisten dan memperlihatkan harga lama, harga acuan baru, harga diajukan, qty/roll yang dirujuk dan keputusan persetujuannya.

Untuk Special Order yang mereferensikan produk induk, harga Grade A tetap arah yang Anda putuskan sebelumnya. Namun preview harga OD saat ini menghitung biaya hasil sample ditambah margin; ini belum membuktikan harga induk Grade A otomatis dipakai. Penyelarasan sumber harga dibutuhkan bila arah itu disahkan sebagai implementasi. [E05: backend/services/special_order_phase2.py:190](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/special_order_phase2.py#L190).

Tidak ditambahkan toleransi variance otomatis; pilihan genapkan atas/bawah dan keputusan qty final tetap mengikuti arahan Anda sebelumnya. Semua kewenangan tetap melalui Custom Role/Access.

## 3. MD Quality: hubungan receiving, RFID dan potongan uji

**Jawaban Anda:** “form md quality itu diambil / disesuaikan dan sama dari barang masuk/form barang masuk ... bebas bisa memilih roll mana yang dipotong ... hanya 1 setiap lotnya atau semua roll dicek”. Anda meminta urutan terbaik terhadap pemberian RFID.

**Koreksi teknis yang penting:** pada kode yang diperiksa, chip RFID ditulis **EPC sebagai identitas**, bukan angka qty receiving. Angka qty yang tampak pada label adalah teks hasil cetak. Ketika EPC dibaca, sistem mencari tag lalu roll di database. Saldo qty operasional mengikuti roll. Jadi perubahan qty tidak memerlukan identitas roll baru. [E10: backend/services/rfid_print_service.py:47](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/rfid_print_service.py#L47); [E11: backend/services/rfid_ingest_service.py:179](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/rfid_ingest_service.py#L179). Pemisahan EPC sebagai identitas juga konsisten dengan penjelasan [GS1 tentang EPC/RFID](https://www.gs1.org/standards/rfid).

| Data | Contoh ilustrasi | Fungsi |
|---|---|---|
| ID/RTN roll | ROLL-001 | Identitas roll fisik yang tetap |
| EPC | kode unik tag yang terikat ROLL-001 | Kunci untuk menemukan roll |
| Qty penerimaan bruto | 100 yard | Riwayat barang yang benar-benar diterima |
| Pemakaian MD Quality | 0,25 yard | Pengurangan untuk uji, terhubung ke receiving/INS/roll |
| Saldo roll | 99,75 yard | Qty yang masih ada setelah uji |
| Teks label | 100 yard atau 99,75 yard menurut waktu cetak | Informasi manusia; dapat menjadi usang bila saldo berubah |

Angka di atas hanya contoh, bukan data perusahaan. Jumlah roll tetap satu selama pengambilan potongan uji tidak melahirkan roll stok terpisah. Potongan yang habis untuk pengujian dicatat sebagai pemakaian/waste uji, bukan penjualan sample.

**Urutan yang saya rekomendasikan:**

1. **Barang diterima di transit.** Input/konfirmasi SJ supplier, PO/MKO, LOT dan qty fisik tiap roll. Catat qty bruto sebelum dipotong untuk pengujian.
2. **Identitas roll terbentuk.** Roll mendapatkan identitas unik; daftar receiving menjadi sumber daftar MD Quality. Hindari mengetik ulang artikel/warna/roll secara bebas.
3. **RFID dipasang dan diverifikasi.** Ikat EPC ke roll sebelum roll dipindahkan atau dibawa untuk pengambilan sample. Pembentukan EPC di database saja belum membuktikan tag fisik telah terpasang dan terbaca.
4. **MD Quality memilih roll.** Tampilkan semua roll penerimaan beserta LOT, lalu pilih roll yang diuji. Bisa satu per LOT atau semua, sesuai keputusan petugas yang berhak. Catat roll yang benar-benar dipotong dan cakupan penilaian; jangan menandai semua roll sudah diperiksa fisik bila hanya sampling.
5. **Potong dan catat pemakaian aktual.** Rekam panjang potong, satuan input, qty pengurang satuan stok, faktor/sumber konversi dan referensi inspeksi. Pengulangan klik/scan tidak boleh mengurangi dua kali.
6. **Isi dua hasil MD Quality.** Warna/labdip: sesuai/tidak sesuai; handfeel: sesuai/tidak sesuai. Keputusan terima/tolak diinput petugas berhak setelah pembahasan nyata, sesuai arahan Anda. Tidak dibuat proses rapat owner di ERP.
7. **Perbarui saldo dan tampilan label.** Database mencatat saldo baru tanpa menghapus angka bruto penerimaan. Bila label mencantumkan saldo, perbarui teks label secara terkendali; jangan menempelkan dua tag aktif untuk satu roll hanya karena qty berubah. Tata cara cetak ulang/penggantian label perlu diverifikasi pada printer/middleware, bukan dianggap telah selesai.
8. **Lepas ke penyimpanan/cross-dock setelah syarat terpenuhi.** Status diterima, tag terverifikasi dan keputusan MD Quality harus terbaca terpisah. Roll yang ditahan tidak ikut dipenuhi/dikirim sebagai stok bebas.

**Mengapa tag lebih dulu?** Pemilihan roll oleh MD Quality sudah dapat memakai scan identitas yang sama dengan gudang. Qty tetap dapat berubah setelah pengujian. Jika operasional memilih MD Quality sebelum cetak tag final, itu juga mungkin, tetapi roll harus sudah mempunyai identitas sementara yang dapat dipindai dan tidak pernah tercampur. Tidak ada alasan teknis untuk menahan pembuatan identitas hanya karena qty akan berkurang.

**Keadaan sekarang:** identitas/saldo roll memang terbentuk di receiving; ada konfigurasi auto-RFID saat scan dan alur print/verify. INS dapat dibuat otomatis ketika penerimaan masuk `qc_pending`; pembentukan ini bergantung pada jalur/kebijakan receiving, sehingga tidak dinyatakan selalu terjadi pada semua penerimaan. MD Quality dan QC sudah dipisahkan dalam hasil per baris. Namun fungsi simpan hasil MD Quality yang diperiksa mencatat hasil kualitas/hold; belum mengerjakan seluruh transaksi potong-uji dan pengurangan qty seperti flow di atas. [E08: backend/services/receiving_roll_service.py:68](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/receiving_roll_service.py#L68); [E09: backend/services/inbound_complete_service.py:569](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/inbound_complete_service.py#L569); [E12: backend/services/rfid_print_service.py:21](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/rfid_print_service.py#L21); [E13: backend/services/inspection_service.py:718](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/inspection_service.py#L718).

**Knitting kg:** interval/panjang potong boleh yard, tetapi pengurangan stok kg harus memakai hasil ukur/faktor konversi yang sah. Resolver satuan tersedia, tetapi produk berbasis kg tidak otomatis menyelesaikan yard→kg hanya dengan mengisi GSM/lebar pada semua jalur. Jangan memakai angka 0,25 yard sebagai 0,25 kg. Faktor yang tidak tersedia harus terlihat sebagai data belum lengkap. [E33: backend/services/uom_service.py:389](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/uom_service.py#L389). Catatan ini meneruskan hasil uji terfokus sebelumnya, bukan permintaan mengganti aturan potong.

## 4. Permintaan QC sebelum kirim dan Meja QC

**Jawaban Anda:** seluruh roll maupun sampling boleh, dipilih pada permintaan QC; Anda mengusulkan toggle checkout default tidak QC dan Meja QC.

Interpretasi yang dicatat:

- Pada checkout, Sales mencatat apakah SO ini diminta QC customer; default permintaan adalah tidak.
- Ketika diminta, pilih cakupan seluruh roll atau sampling dan catatan kebutuhan. Pemilihan jumlah/roll sampling dilakukan dalam permintaan/persiapan QC, bukan ditebak otomatis dari seluruh stok gudang.
- Jika sebelumnya customer memiliki ketentuan wajib QC, ketentuan itu tidak boleh hilang hanya karena default toggle tidak. Prioritas aturan wajib, jika nantinya dipakai, ditampilkan jelas dan tetap mengikuti konfigurasi/hak akses. Ini catatan konsistensi, bukan mengasumsikan daftar customer wajib sudah tersedia.

**Flow yang diusulkan:** checkout minta QC → Admin Sales finalisasi alokasi roll → permintaan masuk Meja QC dengan referensi SO dan roll aktual → QC memeriksa cakupan yang diminta → hasil lulus/gagal ditindaklanjuti → validasi muat → kirim. Sesudah alokasi diganti, hasil roll lama tidak dapat dianggap hasil roll pengganti.

Meja QC dapat memakai fondasi hub inspeksi yang sudah ada. Tampilkan sumber pekerjaan, SO/customer, lokasi/gudang, tanggal rencana kirim, jumlah roll yang harus dicek, petugas dan status hasil. Usulan status: menunggu alokasi, menunggu pemeriksaan, dikerjakan, selesai/menunggu keputusan; nama final mengikuti tampilan aplikasi.

**Keadaan sekarang:** jenis inspeksi mencakup receiving/makloon, retur dan random check; jenis permintaan QC sebelum kirim dari SO belum tercantum dalam daftar jenis yang dibaca. Random check sekarang mengambil stok `available` bebas reservasi secara acak. Karena itu random check tersebut belum dapat dianggap sudah memenuhi pemeriksaan roll reserved milik SO. Form/layanan dan antrean yang ada dipakai sebagai fondasi. [E15: backend/services/inspection_service.py:48](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/inspection_service.py#L48); [E16: backend/services/inspection_service.py:892](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/inspection_service.py#L892).

Hasil QC fisik dan Final Loading Check berbeda: QC menilai mutu roll; loading check memastikan identitas/qty muatan sesuai dokumen. Keduanya dapat diperlukan untuk SO yang sama tanpa saling menggantikan.

## 5. Form DATA HASIL INSPECT dan sumber roll

**Jawaban Anda:** nama kain ditaruh pada kolom; nama customer pada header; jenis kain woven/knitting; warna internal dan supplier; ID roll; periode adalah tanggal pemeriksaan. Tiga sumber pemeriksaan: SO permintaan customer, retur dan random melalui scan.

| Bagian form | Isi yang dipahami | Sumber/aturan |
|---|---|---|
| Judul | DATA HASIL INSPECT | Nama form |
| Header tanggal | Tanggal pemeriksaan | Tanggal pekerjaan inspect aktual, bukan otomatis tanggal SO/receiving |
| Header customer | Nama customer | Dari SO/retur terkait; random stok dapat tanpa customer dan harus diberi keterangan, bukan diisi customer fiktif |
| Header supplier | Nama supplier asal barang | Receiving/LOT asal; bila lebih dari satu asal, kelompokkan atau tampilkan sesuai baris yang relevan |
| Header jenis kain | Woven / Knitting | Dari master artikel yang diperiksa; bukan nama customer |
| Kolom nomor | Nomor urut pemeriksaan | Satu baris utama mewakili satu roll |
| Kolom nama kain | Nama artikel/kain | Menggantikan fungsi kolom CUSTOMER pada contoh fisik |
| Kolom identitas roll | ID/RTN roll | Identitas unik, tersambung ke hasil scan dan stok |
| Kolom warna | Warna KN dan nama/kode warna supplier | Ditampilkan berlabel agar tidak tertukar; data supplier boleh kosong dengan penjelasan bila belum direkam |
| Kolom qty | Qty roll dan satuan stok | Yard atau kg; panjang inspect yard tetap dibedakan dari kg |
| Kolom interval | 0–15, 15–30, 30–45, ... 135–150 yard | Posisi cacat sepanjang kain, selalu yard |
| Isi tiap interval | Jenis cacat, bobot poin dan jumlah/kejadian sesuai data form | Model akhir menunggu validasi kamus cacat dan formula; jangan hanya menyimpan total sehingga posisi hilang |
| Hasil | Poin hasil per roll, grade hasil dan qty sesuai satuannya | Perhitungan final belum ditetapkan dari foto saja |
| Perbaikan/Keterangan | Tindakan dan catatan petugas | Dapat diedit sesuai akses, riwayat terjaga |

**Sumber daftar roll:**

1. **QC SO:** pilih SO → tampilkan roll alokasi aktual SO → pilih seluruhnya atau subset untuk sampling. Jangan mengambil roll lain yang artikelnya sama tetapi tidak dialokasikan pada SO itu.
2. **QC retur:** sumbernya barang yang benar-benar diretur dan diterima, terhubung dokumen retur. Kebijakan retur dibahas terpisah; di sini hanya sumber identitasnya.
3. **QC random fisik:** petugas memilih aktivitas random check lalu scan roll yang diambil → resolve EPC/RTN ke roll → validasi lokasi, entitas, status dan apakah sedang dipakai proses lain → baru masuk daftar pemeriksaan. Scan yang sama tidak menggandakan baris. Jika terikat SO, jangan mengambilnya diam-diam sebagai stok bebas.

**Keadaan sekarang:** INS sudah dapat bersumber penerimaan dan retur. Form per roll sekarang menerima jumlah cacat per bobot 1/2/3/4 lalu mengirim agregat count; ini belum menyimpan peta posisi cacat pada setiap interval 15 yard sebagaimana tabel client. Random check existing memilih kandidat secara acak dari database, berbeda dengan tambahan cara scan fisik yang Anda jelaskan. [E34: backend/services/inspection_service.py:521](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/inspection_service.py#L521); [E17: frontend/src/features/inspections/InspectLineModal.jsx:81](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/frontend/src/features/inspections/InspectLineModal.jsx#L81); [E16: backend/services/inspection_service.py:892](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/inspection_service.py#L892).

## 6. Arti panjang kain, sepuluh interval dan legenda

**Jawaban Anda:** “panjang kain apa? ... per 15 yard ... sepuluh kolom ... maksimal 150 yard, legenda ... keterangan?”

Ya, **legenda yang saya maksud adalah bagian KETERANGAN pada bawah form**: arti kode cacat dan bobotnya. Bukan jenis dokumen atau proses tambahan.

Panjang yang saya maksud adalah **panjang roll yang benar-benar diperiksa oleh mesin**, dalam yard. Jika qty stok roll sudah yard, nilainya dapat berasal dari ukuran roll itu. Jika roll dijual/disimpan kg, panjang inspect yard tetap diperlukan sebagai ukuran pemeriksaan dan posisi cacat; tidak boleh menyebut kg sebagai posisi panjang. Tidak perlu menanyakan panjang yang sama dua kali bila datanya sudah ada dan benar.

Sepuluh kolom 15 yard adalah pembagian posisi pada satu tampilan/form: 0–150 yard. Roll 108 yard hanya memakai interval sampai posisi 108; sisanya tidak diperiksa, bukan otomatis nol cacat. Jika ada roll melebihi 150 yard, usulan tampilan adalah lembar/kelanjutan interval berikutnya dengan ID roll yang sama, bukan memotong catatan di 150 atau membuat roll fiktif baru.

**Formula belum dapat dinyatakan benar:** interval posisi, jumlah kejadian cacat, bobot poin dan nilai hasil akhir adalah data yang berbeda. Kode sekarang menghitung Σ(bobot poin × jumlah), lalu membandingkan ke ambang grade. Itu belum membuktikan sama dengan hitungan pada form perusahaan. Saya tidak menetapkan pembagi panjang/lebar, angka ambang atau rumus normalisasi baru. [E14: backend/services/qc_inspection_service.py:42](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/qc_inspection_service.py#L42).

Yang menunggu client: kamus kode cacat yang sah dan contoh satu roll lengkap beserta cara menghitung angka hasil sampai grade. Tidak diperlukan pengulangan pertanyaan panjang yang sudah Anda jelaskan. Kebutuhan layout tetap bisa dicatat tanpa mengarang formula.

## 7. Dual naming LOT

**Jawaban Anda:** “lot dari suplier ... lot 234 ... di KN ... lot A ... perlu konfirmasi kembali, buatkan pertanyaan untuk klien”.

Interpretasi sementara: supplier mempunyai nomor LOT asal; KN mungkin menggunakan nama LOT operasional sendiri untuk kelompok fisik yang sama. Kode supplier tidak diganti/dihapus karena berguna saat klaim, penerimaan dan telusur sumber.

**Keadaan sekarang:** `inventory_lots` sudah memisahkan `lot_number` internal dan `supplier_lot`, ditambah informasi lain seperti dye lot. Nomor LOT internal yang dibentuk otomatis bukan format A/B yang diasumsikan dari contoh. Metadata supplier LOT dapat diubah melalui jalur yang diizinkan; itu tidak berarti nomor identitas internal bebas diganti. [E18: backend/services/lot_service.py:165](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/lot_service.py#L165); [E19: backend/services/lot_service.py:530](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/lot_service.py#L530).

Jadi fondasinya ada. Yang belum dipastikan adalah apakah A merupakan alias tampilan atau nomor LOT bisnis yang benar-benar diinginkan, serta cara mempertahankan pemetaannya pada penerimaan berikutnya. Pertanyaan lengkap siap dibawa ke client ada pada dokumen 04. Belum dibuat keputusan skema nomor baru.

## 8. Gudang, transit, SJ dan satu dispatch banyak SO

**Pemahaman utama:** satu **Lokasi** seperti Rancamalang memiliki beberapa **Gudang**. Driver/helper mengumpulkan roll berdasarkan picking list, kembali ke gudang transit, validasi scan, lalu dokumen keberangkatan disahkan. Satu armada boleh membawa banyak SO. Jakarta dapat menjadi lokasi transit berikutnya sebelum customer.

**Penilaian:** arah operasional ini masuk akal. Dokumentasi Dynamics 365 menunjukkan satu load dapat memuat beberapa SO dan pengiriman dapat melalui hub dengan load lanjutan. Ini mendukung pola Anda, tetapi tidak menetapkan aturan universal bahwa setiap perusahaan wajib menerbitkan SJ tepat satu per SO. [Load beberapa SO](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/confirm-and-transfer), [Hub consolidation](https://learn.microsoft.com/en-us/dynamics365/supply-chain/transportation/plan-loads-hub-consolidation).

**Penyempurnaan yang saya usulkan:**

- **Picking list:** pekerjaan pengambilan dari gudang/rak sumber. Bukan bukti barang sudah diserahkan ke customer.
- **SJ:** isi barang aktual untuk satu SO pada satu keberangkatan/rute tujuan dan entitas penerbit. Bila SO dikirim sebagian atau berangkat lagi dari Jakarta, wajar ada SJ lain yang saling terhubung. Jadi rumusan yang lebih tepat: **SJ per SO per keberangkatan yang relevan**, bukan satu nomor seumur hidup SO.
- **Dispatch Notes/manifest armada:** seluruh dokumen dan barang yang berada dalam satu perjalanan armada. Mencakup beberapa SO/SJ; bila diperlukan juga dokumen transfer/internal purchase yang sah.
- **SJ transit/internal:** menyertai barang ke lokasi internal, referensi transfer dan SO kebutuhan tetap ada. Tidak diperlakukan sebagai serah terima akhir customer.
- **SJ Jakarta→customer:** nomor baru untuk keberangkatan fisik berikutnya, terhubung dokumen asal/leg sebelumnya. Tidak mencatat penjualan customer yang sama dua kali.

**Keadaan sekarang:** sudah ada picking, SJ, final loading check, transfer antar-gudang dengan penerimaan per roll serta modul logistik/armada. Namun kode logistik menolak beberapa `order_id` dalam satu pengiriman. SJ saat ini dibentuk per tugas/product/gudang; belum sama dengan konsolidasi semua produk SO di transit. Pemeriksaan muat sekarang beracuan SO+gudang, sehingga belum otomatis pemeriksaan seluruh isi armada lintas SO. [E20: backend/services/logistics_service.py:144](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/logistics_service.py#L144); [E21: backend/services/shipment_service.py:94](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/shipment_service.py#L94); [E23: backend/services/loading_check_service.py:158](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/loading_check_service.py#L158); [E26: backend/services/transfer_receipt_service.py:236](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/transfer_receipt_service.py#L236).

**Dampak penting yang ditemukan saat menelusuri rantainya:** dispatch penjualan sekarang memperbarui status SO dan memanggil posting pendapatan/HPP. Karena itu jangan menggunakan dispatch penjualan existing untuk perpindahan Bandung→Jakarta transit tanpa membedakan tujuan transaksinya. Persoalannya bukan hanya mengganti nama SJ atau menambah tombol cetak. Perjalanan internal, komitmen stok SO, dan pemenuhan customer perlu terbaca terpisah. Ini analisis dampak kode, bukan penetapan kebijakan pengakuan pendapatan baru. [E22: backend/services/shipment_service.py:132](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/shipment_service.py#L132).

Detail langkah, input/output dan matriks dokumen ada di **02_Alur_Logistik_Transit_dan_Dokumen.md**. Pembelian antar-entitas tetap transaksi kepemilikan tersendiri; transfer fisik bukan pengganti jual beli internal. [E25: backend/services/transfer_receipt_service.py:73](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/transfer_receipt_service.py#L73).

## 9. Kekurangan roll dan amandemen SO diputus per kasus

**Jawaban Anda:** pengiriman barang pengganti atau hanya menyelesaikan roll yang ada diputus per kasus; bila qty final berbeda, SO diamandemen.

Aturannya tidak perlu diubah menjadi toleransi qty otomatis. Sistem menyajikan fakta dan pilihan yang sah bagi petugas berhak:

1. Catat roll dikirim, roll diterima, yang belum tiba/rusak/salah serta qty fisik aktual.
2. Roll belum tiba tetap ditelusuri pada transfer/exception; jangan ditandai sudah diterima agar dokumen cepat selesai.
3. Jika menunggu barang/roll pengganti, sisa pemenuhan SO tetap terbuka. Penggantian qty/roll harus diperiksa dan harga mengikuti hasil final/approval yang relevan.
4. Jika disepakati hanya roll yang ada, lakukan amandemen SO dan penyesuaian dokumen komersial yang terkait. Amandemen SO tidak otomatis menghapus kehilangan barang di perjalanan; kehilangan fisik tetap harus diselesaikan pencatatannya.
5. Invoice, piutang dan pembayaran mengikuti dokumen final yang sah; pembayaran yang sudah masuk tidak dihapus/dikirim ulang seolah belum pernah terjadi.

**Keadaan sekarang:** penerimaan transfer aktual, status parsial dan exception tersedia. Ini dapat dipakai sebagai fondasi. Penyelesaian kebutuhan customer dan penanganan barang hilang tidak boleh dianggap satu tombol yang sama. [E26: backend/services/transfer_receipt_service.py:236](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/transfer_receipt_service.py#L236); [E07: backend/services/so_override_service.py:316](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/so_override_service.py#L316).

## 10. Cutoff pembayaran antar-entitas

Belum ada tanggal cutoff dari client. Aturan yang sudah jelas tidak ditanyakan ulang: perpindahan/transaksi dapat berlangsung lebih dahulu, dibayar penuh per transaksi, tidak memakai netting. Yang menunggu adalah pengelompokan periode pembayaran dan dasar tanggalnya.

Pertanyaan client lengkap ada pada dokumen 04. Tidak dibuat asumsi bahwa cutoff otomatis tanggal terakhir bulan, tanggal penerimaan atau tanggal invoice.

## 11. Export seluruh data dan rapor staf

### 11.a — seluruh data bisnis, custom periode dan kolom

Yang Anda maksud adalah semua dataset bisnis yang ada dan boleh diakses user, dengan filter yang relevan, periode tanggal pilihan user, pilihan kolom dan preview. User tidak perlu mengetahui nama collection/database.

Rancangan yang saya usulkan adalah **Laporan & Ekspor** dengan dua pintu: ekspor cepat dari daftar modul dan pembuat laporan lanjutan. Semua hasil yang cocok dengan filter dapat diunduh, tidak hanya halaman preview. Data teknis seperti token/kredensial bukan dataset laporan bisnis; hak entitas/lokasi/field tetap sama dengan tampilan aplikasi, termasuk larangan Sales melihat grade.

**Keadaan sekarang:** export hasil analitik ke Excel serta export KPI designer sudah tersedia. Katalog analitik sudah mengenal customer, produk dan Sales. Jadi kebutuhan join penjualan tidak dimulai dari nol. Tetapi itu belum membuktikan semua dataset, semua field, periode custom dan pilihan relasi/kolom yang Anda minta sudah ada dalam satu antarmuka. [E27: backend/services/analytics_catalog.py:67](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/analytics_catalog.py#L67); [E29: backend/routers/ai_analytics.py:222](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/routers/ai_analytics.py#L222); [E36: backend/routers/rnd.py:750](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/routers/rnd.py#L750).

### 11.b — nilai desain adalah skor

Dicatat sebagai **skor desain**, bukan harga jasa designer, harga kain, biaya sample atau omzet. Kode Design Studio sudah mempunyai skor versi desain dan agregat skor. Nilai 0 yang memang dinilai harus berbeda dari belum dinilai/kosong. Bila ringkasan memakai rata-rata skor versi, label harus menyebut “rata-rata skor versi”, bukan seolah skor final tiap desain. [E31: backend/services/rnd_kpi_service.py:256](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/rnd_kpi_service.py#L256).

### 11.c — join yang berguna dan rapor designer/Sales

Saya koreksi penjelasan sebelumnya: memisahkan arti revisi artwork dan round proofing **tidak berarti harus dipisah file atau sheet**. Jika hubungan bisnisnya memang ada dan berguna, keduanya dapat menjadi kolom berbeda pada laporan Special Order yang sama. Jika tidak ada hubungan, keduanya tidak dipaksa digabung.

Contoh sesuai permintaan Anda:

- Customer A + Sales A + periode pilihan → detail item penjualan customer tersebut yang diatribusikan ke Sales A.
- Artikel A + Sales A/B/C + periode pilihan → detail artikel serta ringkasan per Sales, warna dan satuan.
- Designer A + September/custom tanggal → seluruh desain yang relevan, skor, status, versi dan revisi; disertai ringkasan. Detail pekerjaan dan ringkasan harus dapat direkonsiliasi.
- Sales A + periode → SO, item, qty/roll, nilai pesanan, pemenuhan, uang diterima dan piutang dalam kolom/metrik dengan dasar yang jelas. Nilai order, pendapatan jurnal dan penerimaan uang tidak dijumlah menjadi satu “penjualan”.

**Catatan kode:** KPI designer sekarang punya pilihan periode terbatas, menggabungkan indikator round sample dan Design Studio, serta PDF personal menampilkan 12 round terbaru. Agregat artwork saat ini mengelompokkan berdasarkan nama pembuat dokumen; ini perlu diperhatikan bila pekerjaan berpindah designer. Rapor lengkap yang Anda minta tidak cukup dibuat dengan mengganti judul PDF tersebut. [E30: backend/services/rnd_kpi_service.py:79](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/rnd_kpi_service.py#L79); [E31: backend/services/rnd_kpi_service.py:256](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/rnd_kpi_service.py#L256); [E32: backend/services/rnd_kpi_export.py:442](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/rnd_kpi_export.py#L442).

Rincian kolom, contoh join, pemilihan periode dan pencegahan duplikasi ada di **03_Rancangan_Export_dan_Rapor_Staf.md**. Rancangan merupakan usulan hasil analisis untuk ditinjau, bukan klaim sudah diterapkan.

## Batas keputusan setelah jawaban ini

Yang telah jelas tidak dibuka lagi sebagai pertanyaan umum tentang siapa berwenang: seluruhnya mengikuti konfigurasi Custom Role/Access. Pembahasan retur yang Anda tahan tetap tidak diputuskan. Pertanyaan client yang diminta disiapkan adalah LOT dan cutoff pembayaran. Formula inspect/kamus cacat tetap menunggu data; usulan urutan tagging, dokumen transit dan bentuk export disediakan secara konkret agar dapat ditinjau sebelum menjadi development plan.
