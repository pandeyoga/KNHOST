# Gate RFID — bacaan nyasar (unintended read), photo-eye, dan syarat sebelum membangun

> **WAJIB DIBACA** sebelum mengubah `middleware/` (U300 Reader Agent), logika gate ERP
> (`backend/services/gate_evaluator.py`, `rfid_ingest_service.py`, `rfid_service.py`, router `rfid`), atau menerapkan
> patch `middleware/u300-erp-integration-0.5.0/`.
>
> **Pemilik (8 Nov 2026):** soal bacaan nyasar & photo-eye harus diselesaikan dulu **sebelum membangun atau merevisi**
> middleware dan logika gate. Selama butir di §6 masih terbuka → **STOP & ASK** (tanya pemilik), jangan menebak.

Dokumen ini adalah satu-satunya sumber bersama untuk konteks ini. Pembahasan aslinya ada di satu sesi chat
Claude Code (26–27 Okt 2026) yang tidak bisa dibaca sesi lain.

| Sumber | Isi |
|---|---|
| [`riset/Mitigasi unintended read RFID gate.md`](riset/Mitigasi%20unintended%20read%20RFID%20gate.md) | Laporan riset mendalam 27 Okt (fisika RF, regulasi, praktik industri, 13 usulan perubahan ERP, rencana uji & metrik). **Catatan:** laporan ini masih mengasumsikan photo-eye tersedia; fakta pemilik sesudahnya (§1) mengubah itu — bila berbeda, **dokumen ini yang berlaku**. |
| [`riset/catatan/`](riset/catatan/) | Catatan sumber per topik (regulasi & perangkat, studi industri, fisika RF, algoritma penyaringan, logika RFID KNHOST saat itu) beserta tautan rujukan. |
| [`../../middleware/`](../../middleware/) | Kode U300 Reader Agent 0.4.0-lab dan patch ERP 0.5.0 dari PT Kubus (belum diterapkan). |

## 1. Fakta lapangan dari pemilik (27 Okt 2026)
- Gate **IN dan OUT terpisah, masing-masing satu arah**. Bersih ±2,5 m lebar × 2,75 m tinggi × 1,5 m dalam.
- **3 antena per gate: atas, kiri, kanan.** Sudut bisa diatur. Antena masuk ceruk ACP, penutup tidak ada / akrilik.
- Perangkat: reader **Chainway U300** (kemungkinan), antena **Chainway Ant-RC12 12 dBi varian EU (865–868 MHz)**,
  tag **Impinj Monza R6-P**. Panjang kabel dan setelan reader **belum ada**.
- Muatan stacker ±**180 × 180 cm**, tumpuk **menyilang maks 7 lapis (±2 m)**; label di **kiri/kanan dan depan**,
  tidak ada di belakang. Muatan kecil 1–3 roll mungkin ada.
- Kecepatan **≤ 5 km/jam**; berhenti/mundur di gate diatur lewat SOP.
- Dokumen (surat jalan / putaway / transfer) **selalu dibuat sebelum barang lewat**.
- **Photo-eye tidak ada di pengadaan** (konsep baru bagi pemilik). → **Diperbarui 8 Nov 2026: photo-eye masuk
  pengadaan** (K-RFID-01).
- Antena: → **asumsi kerja 8 Nov 2026: varian Indonesia**, yaitu pita yang mencakup 920–923 MHz, bukan varian EU
  (K-RFID-02).
- Middleware dibuat sendiri: reader → middleware → ERP.

## 2. Kesimpulan riset (ringkas; angka = hitungan model, wajib dibuktikan uji lokasi)
- Bacaan nyasar **tidak bisa dihapus** oleh software; software mencegahnya menjadi transaksi salah. Target realistis:
  **tidak ada transaksi salah yang lolos tanpa diperiksa**, bukan nol bacaan nyasar (praktik gudang nyata: galat
  1,5–5 % per tag).
- **Daya**: Indonesia 920–923 MHz, batas ±400 mW EIRP (≈26 dBm). Setelan 30 dBm + antena 12 dBi ≈ 25–30× batas →
  turunkan ke **±15–16 dBm konduksi**. Pada batas legal tag masih terbaca ±2,9–4,6 m, sampai ±6–9 m dengan pantulan
  logam.
- **Antena varian EU** dipakai di luar pitanya → ukur di 920–923 MHz atau ganti varian 902–928 MHz.
- **Reader**: region tabel 920–923 (bukan "920–925"), **session 0, TagFocus mati** (tag diam terus melapor →
  mudah dikenali), kirim bacaan **mentah** (EPC, port antena, RSSI, waktu reader), tanpa dedup di middleware.
- **Tata letak**: gate di dua pintu terpisah (opsi C) paling kuat; berdampingan tanpa shielding (A) layak bila tidak
  aktif bersamaan; partisi/cat/tirai tanpa clear zone (B) paling lemah buktinya.
- Roll tersulit (penentu daya minimum): **label depan** (hanya antena atas yang bisa melihat, bila dimiringkan ke arah
  datang — di gate OUT itu mengarah ke area rak) dan **baris paling atas/bawah** (55–65° dari sumbu antena samping).
  Arah gulungan di stacker sangat menentukan.

## 3. Photo-eye
- **Gunanya untuk gate satu arah:** memberi tahu dengan pasti **kapan** ada muatan di gate dan **apakah benar-benar
  tembus** (sensor A di mulut masuk, B di mulut keluar; A terpotong tanpa B = mundur/batal), memisahkan dua muatan
  beriringan, menandai stacker berhenti di gate. **Tidak** menentukan roll mana yang benar — itu tetap tugas sinyal
  RFID + dokumen.
- **Tanpa photo-eye** sistem tetap bisa jalan, tetapi lintasan ditebak dari rombongan EPC + RSSI: kalibrasi lebih
  lama, antrean "perlu diperiksa" lebih banyak, kasus mundur & muatan beriringan bisa meleset, muatan kecil 1–3 roll
  lebih rawan, SOP harus lebih ketat.
- **Rekomendasi (27 Okt):** rancang logika agar **tetap jalan tanpa photo-eye**, tetapi **usulkan photo-eye sebagai
  tambahan pengadaan** — biayanya kecil dibanding reader + antena; bila sensor rusak, sistem jatuh ke logika RF.
- **Spesifikasi usulan:** through-beam, **2 pasang per gate** (mulut masuk & keluar, berjarak ±1,5 m), tinggi
  40–60 cm, jangkauan ≥ 10 m, keluaran NPN/PNP 12–24 VDC mode **Dark-ON**, ≥ IP67, respon ±1 ms; pemancar dua pasang
  berselang-seling (anti-interferensi); ke input GPI U300 lewat **relay 24 VDC** bila tipe input U300 belum pasti.
  Contoh (referensi, cek datasheet resmi): Autonics BJ10M-TDT, Omron E3Z-T61, Panasonic CX-411. Retro-reflektif 3–4 m
  terlalu mepet untuk 2,5 m.
- **Middleware 0.4.0** sudah punya `gate.sensor_bindings.a/b` (GPI1–GPI4) tetapi semantiknya **arah** (A→B = out,
  B→A = in). Untuk gate satu arah semantiknya perlu diubah menjadi **lewat vs mundur/batal** + buffer bacaan 2–3 detik
  sebelum sinar terpotong (label depan sudah terbaca sebelum muatan masuk).
- **Keputusan pemilik (8 Nov 2026): photo-eye MASUK pengadaan** → K-RFID-01 ditutup. Logika dibangun sebagai
  **"photo-eye utama + cadangan RF"**: lintasan dibuka/ditutup oleh sensor, logika RF (§4 butir 2) dipakai bila
  sensor rusak/tidak terbaca. Spesifikasi di atas (2 pasang through-beam per gate) menjadi acuan pengadaan; jumlah
  pasang & tipe sensor belum dikonfirmasi terpisah oleh pemilik.

## 4. Usulan logika gate (arah rancangan, belum disetujui formal; semua angka = titik awal kalibrasi)
Prinsip: tiap bacaan dinilai berlapis, hasilnya status — **kosong / kandidat → terkonfirmasi / perlu diperiksa /
batal**. Tidak ada bacaan yang langsung dibuang, tidak ada yang langsung jadi transaksi.
1. **Daftar latar per gate** (pengganti "dwell time"): yang terbaca saat gate kosong dicatat sebagai penghuni latar
   (+ RSSI & antena biasanya) dan diabaikan; lepas dari daftar bila sinyal melonjak jauh / terlihat antena yang biasanya
   tidak melihatnya; tag "nyasar kronis" dilaporkan ke supervisor agar rak/barang dipindah.
2. **Pemicu lintasan:** photo-eye bila ada; cadangan = rombongan EPC baru non-latar bersinyal kuat dalam ±1,5 s.
   Tutup bila tidak ada bacaan **kuat** 2–3 s (bacaan latar tidak memperpanjang). Terbuka > 30–60 s → perlu diperiksa.
3. **Per EPC dalam lintasan:** bukan latar? sinyal setara tag di dalam gate (roll ±40–60 cm vs rak ≥ 3 m ≈ 15 dB lebih
   lemah)? bentuk sinyal naik–puncak–turun bersamaan lintasan? ada di dokumen aktif gate itu?
4. **Lintasan terikat dokumen** (dokumen selalu ada sebelum barang lewat): cocokkan ke dokumen dengan irisan terbanyak,
   deteksi roll yang seharusnya lewat tetapi tidak terbaca.

| Kejadian | Hasil yang diharapkan |
|---|---|
| Orang / forklift kosong lewat | lintasan kosong, tanpa transaksi & tanpa alarm (dengan photo-eye); tanpa photo-eye tidak membuka lintasan |
| Orang membawa 1–2 roll | muatan kecil: ada di dokumen → terkonfirmasi; tidak → perlu diperiksa |
| Roll kuat tetapi tidak di dokumen | perlu diperiksa / alarm (kejadian nyata, bukan nyasar) |
| Tag rak terbaca saat lintasan | latar + lemah + datar + bukan dokumen → diabaikan, dicatat log |
| Logam (forklift/stacker) memantulkan sinyal ke rak | pantulan ±≤6 dB vs jarak ±15 dB → umumnya gugur di sinyal; terburuk masuk antrean periksa. **Wajib ada skenario uji khusus.** |

## 5. Celah ERP KNHOST (pembacaan kode 27 Okt) & rencana
Celah: tag diam memperpanjang jendela lintasan 10 s (muatan berikut tergabung); cap "sudah keluar" dipasang saat roll
sekadar terbaca (maju-mundur → alarm "sudah pernah keluar"); alarm merah per tag; RSSI/antena/waktu reader disimpan
tetapi tidak dipakai; ambang ditanam di kode; tidak ada status "perlu diperiksa"; roll dokumen yang tidak terbaca
tidak terdeteksi di gate. Sejak itu (4 Nov, P18) `gate_evaluator` juga mengenali Order Makloon & Perbaikan.

- **Tahap 1 (ERP, tanpa perangkat):** logika lintasan (bacaan ulang tidak memperpanjang, tutup saat sepi bacaan kuat,
  waktu dari reader) · status lintasan + kios kuning · cap keluar saat terkonfirmasi · lintasan terikat dokumen (pakai
  ulang mesin sesi verifikasi handheld) · alarm berbasis bukti · ambang ke Pengaturan per gate · antrean periksa
  admin gudang dengan bukti · log, masa simpan & **replay**.
- **Tahap 2 (middleware & perangkat):** kontrak data diperluas (ringkasan EPC×antena per 250–500 ms, peristiwa
  lintasan, peristiwa photo-eye, nomor urut & versi konfigurasi) · konfigurasi per gate (peta port, daya per antena,
  session, region, ada/tidaknya photo-eye) · daftar latar & skor per EPC · dukungan photo-eye opsional · sambungan ke
  transaksi (gate IN → konfirmasi tiba putaway/transfer; gate OUT → bukti kirim).
- Rincian & metrik uji (M1–M11, semua **usulan, belum disepakati**): laporan riset §"Modul gate KNHOST…" dan §"Uji
  lapangan…".

## 6. Yang harus diputuskan / diselesaikan DULU (STOP & ASK)
| ID | Hal | Pemutus | Status |
|---|---|---|---|
| K-RFID-01 | Photo-eye masuk pengadaan? (rekomendasi: ya, 2 pasang through-beam per gate) — menentukan apakah logika dibangun "photo-eye utama + cadangan RF" atau "RF saja" | Pemilik | **ditutup 8 Nov 2026 (pemilik; dikonfirmasi ulang di sesi lokal)**: photo-eye masuk pengadaan → logika "photo-eye utama + cadangan RF" |
| K-RFID-02 | Antena varian EU: ukur di 920–923 MHz atau ganti varian 902–928 MHz | Pemilik / teknis | **asumsi kerja 8 Nov 2026 (pemilik; dikonfirmasi ulang)**: antena varian Indonesia (pita mencakup 920–923 MHz); kinerja tetap diukur saat commissioning |
| K-RFID-03 | Uji meja SDK U300 (±30 menit): RSSI **per bacaan** lewat **SDK** (bukan hanya aplikasi demo), satuannya (dBm?), nomor antena, waktu baca, daya per antena. Bila RSSI tidak keluar lewat SDK, lapisan sinyal gugur → photo-eye makin penting | Teknis (PT Kubus) | terbuka — lakukan **sebelum pengadaan final** |
| K-RFID-04 | Tata letak gate (opsi A/B/C), clear zone & jarak rak terdekat, terutama jalur datang di gate OUT | Pemilik | **sebagian 8 Nov 2026**: campuran — ada pasangan IN/OUT **berdampingan dengan sekat** (opsi B) dan ada yang **pintunya berjauhan** (opsi C). Sistem menyimpan tata letak per pasangan gate; pasangan berdampingan butuh aturan penengah (interlock/arbitrasi, usulan riset #10) dan efek sekat wajib dibuktikan uji. Clear zone & jarak rak per gate masih terbuka |
| K-RFID-05 | Setelan reader & kabel: panjang/jenis kabel, daya per port, peta port → antena atas/kiri/kanan, region 920–923 | Teknis | terbuka |
| K-RFID-06 | SOP operator: kecepatan pelan & konstan ≤ 5 km/jam, tidak berhenti/mundur di gate, satu muatan per lintasan, arah gulungan di stacker | Pemilik / operasional | **disetujui sebagai DRAF 8 Nov 2026** — difinalkan setelah uji lapangan; pelanggaran SOP → "perlu diperiksa" |
| K-RFID-07 | Pemetaan 13 usulan (§5) terhadap yang sudah dikerjakan PT Kubus di Agent 0.4.0 + patch ERP 0.5.0, lalu putuskan basis pengembangan (patch Kubus vs `gate_evaluator` KNHOST) | Implementer → pemilik | **ditutup 8 Nov 2026 (pemilik): GABUNGAN** — aplikasi reader & transport Kubus V2 + aturan bisnis `gate_evaluator` KNHOST + lapisan lintasan baru (photo-eye, ringkasan bacaan, daftar latar, status kuning); jalur lama `/api/rfid/ingest` ditutup untuk reader V2 ([audit](AUDIT_MIDDLEWARE_RFID_2026-11-08.md) §5) |
| K-RFID-08 | Target penerimaan uji lapangan (M1–M11) | Pemilik | usulan, belum disepakati |
| K-RFID-09 | Kebijakan alarm: mana yang **merah terkunci** (pelanggaran) vs **kuning/perlu diperiksa** tanpa mengunci (roll kurang, capture tidak lengkap, waktu, tanpa manifest); satu kunci per gate. Kode Kubus kini mengunci semua non-hijau dan berantai (audit AUD-MW-03) | Pemilik | **ditutup 8 Nov 2026 (pemilik): merah terkunci HANYA untuk pelanggaran nyata** (roll tanpa dokumen, karantina, sudah keluar, dokumen batal, EPC asing bersinyal kuat). Roll kurang / capture tidak lengkap / waktu tidak tervalidasi / tanpa manifest = **kuning**: barang jalan, masuk antrean periksa, gate tidak terkunci. **Satu kunci per gate**; simpan daftar alasan, bukan satu kode yang ditimpa |
| K-RFID-10 | Muat multi-trip stacker: dinilai **per lintasan terhadap seluruh SJ** (kode Kubus kini) atau **sesi dokumen akumulatif** — roll kurang dinilai saat dokumen ditutup (audit AUD-MW-22) | Pemilik | **ditutup 8 Nov 2026 (pemilik): SESI DOKUMEN BERTAHAP** — tiap trip hijau bila semua roll kuat non-latar milik dokumen aktif & belum pernah lewat; roll yang belum lewat dinilai saat dokumen ditutup/dikirim |

| K-RFID-11 | Cara menandai **stok lama** | Pemilik | **arah diputuskan 8 Nov 2026**: data stok lama TIDAK dapat diandalkan → tagging = **opname awal / pendaftaran ulang dari fisik** per gedung (lihat §8); cara menulis/menautkan tag menunggu cek keunikan EPC tag yang dibeli |

Yang **boleh** dikerjakan tanpa menunggu: analisis/dokumen (mis. K-RFID-07), dan uji meja K-RFID-03 bila perangkat
tersedia. Perubahan kode middleware/gate hanya setelah pemilik menyatakan butir terkait ditutup — catat keputusannya
di tabel ini (tanggal + siapa).

## 7. Fondasi ERP gudang & putaway untuk gate — keputusan pemilik 8 Nov 2026
Ditanyakan di sesi lokal 8 Nov (status sekarang + tujuan dijelaskan per pertanyaan). Prinsip pemilik: **data lokasi &
gedung belum tervalidasi → semua hal di bawah dibuat BISA DIKONFIGURASI**, bukan ditanam di kode.

| ID | Hal | Keputusan |
|---|---|---|
| K-GDG-01 | Gedung yang memakai gate fisik | **Hanya gedung penyimpanan** — di Rancamalang dan Soreang. Dibuat **bisa diatur per gedung** (punya gate atau tidak, perangkat IN/OUT, mode konfirmasi gate/handheld). Jakarta & gedung tanpa gate = handheld. Penanda `gate_config.physical_gate` kini hanya disimpan → harus dipakai sistem |
| K-GDG-02 | Fungsi gate terhadap transaksi | **Gate IN gedung simpan memvalidasi putaway dari GRN**: lintasan terkonfirmasi otomatis mencatat tiba putaway; roll tak terbaca tetap "belum tiba". **Gate OUT memvalidasi barang keluar** (SJ, transfer, makloon, perbaikan) per trip (K-RFID-10). **Handheld = cadangan** untuk tag tak terbaca (dan alat utama di gedung tanpa gate) |
| K-GDG-03 | Masa awal | **Langsung gate utama** — tanpa periode uji dobel gate + handheld |
| K-GDG-04 | Area QC / inspeksi | **Bisa diatur** (tempat baru bisa muncul). Kondisi sekarang di Rancamalang: **gedung Retur = tempat inspeksi** — barang retur masuk ke sana untuk diinspeksi, dan **barang baru masuk yang diminta inspeksi juga dibawa ke sana**. **MD Quality tidak perlu inspeksi**: dicek & dicocokkan manual oleh orang. Inspeksi = pemeriksaan per 15 yard. Catatan: ini menggeser keputusan P9-K2 (Okt: "tidak ada area inspeksi terpisah") — barang baru yang diinspeksi kini berpindah gedung (butuh dokumen & lewat gate) |
| K-GDG-05 | Bentuk penyimpanan | **Campuran per gedung** (rak bertingkat atau petak lantai tumpukan stacker), diatur per gedung/zona; arti & kapasitas "bin" mengikuti |
| K-GDG-06 | Gudang bahan (greige, benang, dsb.) | **Bisa diatur per gedung**: peran "bahan" dan mode pencatatan (per roll bertag atau kuantitas tanpa tag) |
| K-GDG-07 | Kepemilikan gedung antar PT | **Semua gedung dipakai bersama** semua PT; roll tetap milik PT masing-masing |
| K-GDG-08 | Pembagian zona gedung simpan | **Bisa dikonfigurasi** per gedung (kategori / artikel / grade / PT pemilik, boleh kombinasi) |
| K-GDG-09 | Stok yang masih di transit | **Boleh dialokasikan/dijual seperti sekarang** — rencana P9.6 (mengecualikan stok transit) **tidak** dibangun |
| K-GDG-10 | Putaway setelah GRN | **Draf otomatis**: setelah QC lulus sistem menyiapkan draf putaway per gedung tujuan (sesuai aturan zona/gedung), admin cek lalu terbitkan; **tiba bertahap per trip** didukung |
| K-GDG-11 | QC hasil makloon (P18) | **Ikut setelan PO** (`purchasing.qc_on_receipt`) — tidak dibuat setelan terpisah |

Masih terbuka: **penamaan alamat rak/bin** (usulan `LOKASI-GEDUNG-ZONA-RAK-TINGKAT-BIN`, mis. `RCM-WVN-A-R01-T2-B03`),
K-RFID-03 (uji meja SDK), K-RFID-05 (setelan reader & kabel), K-RFID-08 (target uji), K-RFID-11 (cara tag stok lama),
clear zone per gate (K-RFID-04).

## 8. Opname awal (pendaftaran ulang stok dari fisik) — 8 Nov 2026
Latar (pemilik): klien punya stok tetapi **tidak yakin isi gudang & jumlahnya; data lama tidak dapat diandalkan**. Karena
itu tagging stok lama BUKAN menautkan tag ke data lama, tetapi **mendaftarkan ulang setiap roll fisik** (roll + tag lahir
bersamaan) per gedung, lalu gedung itu di-*cutover* sebelum gatenya dinyalakan.

Alur: (1) master produk dirapikan → (2) gedung dibekukan sesuai keputusan K-OPN-03 → (3) per rak/petak: tempel tag + isi
produk (pindai label supplier / pilih), panjang, lot, grade, PT, bin di handheld → roll & tag dibuat sekaligus →
(4) bandingkan dengan data lama per produk per gedung (hilang / temuan / selisih) → (5) Finance setuju, jurnal selisih →
(6) data gedung diganti hasil pendaftaran, opname RFID verifikasi, gate gedung dinyalakan.

| ID | Hal | Keputusan |
|---|---|---|
| K-OPN-01 | Peran data lama | **Hanya referensi/pembanding** (per produk per gedung), bukan acuan. **Master data dirapikan dulu**: kode salah, duplikat, typo diperbaiki sebelum pendaftaran |
| K-OPN-02 | Nilai barang temuan | **Biaya rata-rata** (perilaku bawaan `stock_count_service.surplus_unit_cost`: rata-rata gudang → rata-rata pemilik → harga master produk) |
| K-OPN-03 | Pembekuan gerakan gedung selama pendaftaran | **Diputuskan 8 Nov 2026**: gedung besar **beku per zona/rak** (zona yang sedang dikerjakan ditutup, sistem menolak gerakan dari/ke zona itu; zona lain tetap melayani); gedung kecil **beku penuh**. Lama penutupan ditentukan setelah **uji coba satu rak** mengukur kecepatan tim (roll/jam tempel + input) |
| K-OPN-04 | Sumber panjang roll | **Dari label bila ada**; roll tanpa label ditandai "panjang belum terverifikasi" dan diukur saat diambil/dipotong |
| K-OPN-05 | Keunikan EPC tag yang dibeli | **terbuka** — pemilik belum bisa cek (8 Nov). Cek ±20 tag dari gulungan: EPC bawaan unik → cukup dibaca & didaftarkan; tidak unik → EPC ditulis sistem/printer sebelum ditempel |
| K-OPN-06 | Aturan & proses perbaikan master produk | **Diputuskan 8 Nov 2026**: kode SKU yang salah **tidak diubah** — dibuat produk berkode benar, kode lama dinonaktifkan & ditandai "digantikan oleh" kode induk (stok tidak dipindah karena stok didaftarkan ulang dari fisik; dokumen terbuka berkode lama diselesaikan/dialihkan dulu). Proses: master produk diekspor ke lembar kerja → MD/klien menandai duplikat, typo, kode benar → diimpor sebagai satu batch ber-pratinjau & bisa dibatalkan. Ekspor CSV yang ada (`/master-data/export-products`) belum memuat artikel, warna kode, gramasi/lebar, indikasi duplikat & kolom tindakan |

Yang sudah ada di ERP: modul Opname per roll (`stock_count_roll_service`: potret → pindai → rekonsiliasi → ACC; hilang →
hitung ulang lalu dihapus + jurnal; kode tak dikenal → roll baru saat ACC + jurnal surplus), tata kelola master produk
(`master_governance_service`: pratinjau duplikat dari atribut kanonik, batch + rollback, koreksi nama ber-riwayat; **SKU
tidak bisa diubah** — aturan "SKU stabil"). Celah: data roll temuan diisi penyetuju (bukan di lapangan), kode yang dipindai
belum dijadikan tag RFID roll baru, belum ada mode "pendaftaran awal gedung" + progres per rak, persetujuan massal, penampung
"produk belum dikenali", dan fitur menandai produk duplikat "digantikan oleh" kode induk.
