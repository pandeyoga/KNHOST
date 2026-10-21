# Lembar hasil UAT — ERP Kain Nusantara (KN-UAT-E2E-002 v2.0)

**Tanggal:** Hari 1 ______ · Hari 2 ______  **Kandidat (URL/commit):** ______  **Fasilitator:** ______  **Pencatat:** ______

Status: `L` Lulus · `G` Gagal · `T` Terblokir · `TD` Tidak diuji. Isi nomor dokumen sistem & ID temuan.

## A1 — Sales membuat pesanan di POS

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| A01 | Pelanggan | Pelanggan menyampaikan kebutuhan: artikel, warna, qty + satuan (yard/kg), kirim atau ambil sendiri, perlu … |  |  |  |
| A02 | Sales | Pilih pelanggan Toko Kain Sejahtera · CUST-0001 dan alamat kirim. Pelanggan baru: [Pelanggan Baru]. |  |  |  |
| A03 | Sales | Cari artikel (mis. DENIM TENCEL TAUPE), pilih warna, isi qty & satuan, atau mode Beli per roll (pilih roll … |  |  |  |
| A04 | Sales | Bila qty tidak pas roll: buka opsi genapkan, sampaikan ke pelanggan pilihan ke atas / ke bawah / potong; … |  |  |  |
| A05 | Sales | Isi qty final; pilih Termin Pembayaran (Tunai · CBD · DP 50% · NET 7/14/30/60/90 · Bertahap 3x); Tim Sales & … |  |  |  |
| A06 | Sales | Pilih Metode Pemenuhan: Kirim (tanggal kirim opsional, tidak boleh lewat) atau Ambil di Gudang (wajib … |  |  |  |
| A07 | Sistem | Sistem memeriksa: stok milik entitas penjual, lot campur (minta konfirmasi), limit & tunggakan kredit, … |  |  |  |

## A2 — Verifikasi Admin Sales, persetujuan & konfirmasi

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| A08 | Admin Sales | Buka dialog Verifikasi Kelengkapan: alamat & nama penerima & telepon, syarat bayar, isi pesanan (qty > 0), … |  |  |  |
| A08b | Sales | Lengkapi data yang kurang (alamat penerima, telepon, termin) lalu kembali ke A08. |  |  |  |
| A09 | Admin Sales | Mengajukan SO ke gerbang persetujuan. Bila tidak ada gerbang aktif, sistem menyetujui otomatis. |  |  |  |
| A10 | Manajer | Baca alasan gerbang (nilai/kredit/harga/makloon), bukti lampiran, ringkasan SO. Putuskan per entri: … |  |  |  |
| A11 | Admin Sales | Konfirmasi SO yang sudah disetujui. Ini wewenang Admin Sales (tidak perlu manajer). |  |  |  |

## A3 — Gudang: potong, pick, QC, cek muat & Surat Jalan

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| A12 | Gudang | Buka tugas per gudang; cetak Surat Pengambilan Barang (picking list: alamat simpan, nomor roll, qty, SO). |  |  |  |
| A13 | Gudang | Untuk roll yang dicadangkan sebagian: ukur & potong fisik, isi panjang aktual & sisa/waste, cetak label roll … |  |  |  |
| A14 | Gudang | Scan tiap roll yang diambil; qty pick = panjang roll. Ulangi sampai semua roll baris terambil. |  |  |  |
| A15 | QC | Jika SO meminta QC: Admin Gudang menugaskan SPK; QC [Mulai diperiksa], isi panjang inspect (yard) & cacat … |  |  |  |
| A16 | Gudang | Scan seluruh roll yang naik kendaraan (handheld RFID). Sistem membandingkan dengan manifest SO. |  |  |  |
| A17 | Gudang | Kirim qty yang sudah di-pick. Boleh sebagian bila kebijakan kirim sebagian aktif. |  |  |  |

## A4 — Pengiriman sampai diterima pelanggan

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| A18 | Admin Gudang | Pilih satu atau beberapa SJ (boleh beberapa SO dalam satu armada), mode Ekspedisi (kurir, layanan, ongkir) / … |  |  |  |
| A19 | Sopir | Sopir/petugas memotret barang naik kendaraan lalu menandai dimuat. |  |  |  |
| A20 | Sopir | Ekspedisi: isi nomor resi. Armada: plat & nama sopir wajib; kendaraan otomatis dalam perjalanan. Opsional: … |  |  |  |
| A20b | Admin Gudang | Bila tidak sampai: isi alasan (≥3 huruf). Admin Gudang menjadwalkan ulang (kembali ke Disiapkan). |  |  |  |
| A21 | Sopir | Di lokasi pelanggan: foto bukti terima, nama penerima, waktu terima. |  |  |  |
| A22 | Admin Gudang | Pelanggan menunjukkan kode pickup (diberikan Sales) + nama & no. identitas pengambil. |  |  |  |
| A23 | Admin Sales | Setelah pelanggan konfirmasi terima, tandai SO diterima. Gudang juga berwenang; Sales tidak. |  |  |  |

## B1 — Harga khusus: ajukan, putuskan, ajukan ulang

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| B01 | Sales | Isi harga per satuan yang diminta, qty minimum (opsional), alasan (wajib), lampirkan bukti persetujuan … |  |  |  |
| B02 | Sistem | Menyimpan harga normal vs diminta + versi alokasi (roll & qty saat diajukan). Pengajuan baru untuk produk … |  |  |  |
| B03 | Admin Sales | Verifikasi kelengkapan (A08) lalu ajukan. Admin Sales hanya memantau antrean Menunggu keputusan manajer. |  |  |  |
| B04 | Manajer | Bandingkan harga normal vs diminta, margin, alasan & bukti. Putuskan per entri [Setujui] / [Tolak] + catatan … |  |  |  |
| B05 | Sistem | Harga baris diganti harga khusus; subtotal, DPP, PPN, grand total dihitung ulang; sumber harga = … |  |  |  |
| B06 | Sales | Setelah ditolak: nego ulang dengan pelanggan → ajukan harga baru; atau batalkan pesanan. |  |  |  |
| B07 | Admin Sales | Admin Sales menentukan alokasi roll, qty & harga final. Bila alokasi berubah setelah harga diajukan, ajukan … |  |  |  |

## B2 — Kredit over-limit, ambang nilai & stok makloon

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| B11 | Sistem | Menghitung eksposur pelanggan (piutang + SO terbuka) vs limit kredit, tunggakan lewat jatuh tempo, dan … |  |  |  |
| B12 | Sales | Checkout menampilkan Kredit OK / Peringatan kredit (mendekati limit / ada tunggakan) / Terblokir Kredit / … |  |  |  |
| B13 | Admin Sales | Checklist menampilkan Tidak tertahan batas kredit sebagai peringatan (keputusan kredit milik manajer). |  |  |  |
| B14 | Manajer | Tinjau limit, eksposur, umur piutang; lampirkan bukti (mis. persetujuan direksi). [Setujui] / [Tolak] + … |  |  |  |
| B15 | Sales | Bila ditolak: tawarkan DP/CBD, kurangi qty, atau tunggu pelunasan tunggakan; ajukan ulang. |  |  |  |
| B16 | Finance | Pelunasan tunggakan dicatat (Alur I) → limit tersedia kembali untuk SO berikutnya. |  |  |  |
| B17 | Admin | Ambang nilai SO (min/max → peran). Bawaan sekarang: tanpa ambang. Uji ambang sementara hanya bila disepakati … |  |  |  |
| B18 | Sales | Bila stok yang dipilih sedang dicadangkan untuk makloon, sistem meminta konfirmasi lalu membuat entri … |  |  |  |

## C1 — Backorder & rencana pemenuhan multi-sumber

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| C01 | Sales | Pesan artikel yang stok PT sendiri kurang (contoh uji: ALICE KNIT 14 A, stok hanya di CST, 100 kg). |  |  |  |
| C02 | Sistem | Mencatat baris backorder per produk (qty kurang). SO muncul di Keep & Pending dan antrean Perlu dipenuhi … |  |  |  |
| C03 | Admin Sales | Panel menampilkan stok sendiri per gudang, stok di PT lain + kesiapan harga internal, PO yang sedang … |  |  |  |
| C04 | Admin Sales | Bagi kekurangan per baris: stok sendiri (gudang lain) · transfer dari PT lain (boleh >1 PT) · PO ke supplier … |  |  |  |
| C05 | Admin Sales | Jalur PT lain membuat PIN lalu Transaksi Antar-PT (dokumen kembar penjual-pembeli, contoh KSC/IC-00009). … |  |  |  |
| C06 | Pembelian | Jalur supplier membuat PR dari SO (contoh PR-00042, 40 kg). Dilanjutkan di Alur D (PR → PO → kedatangan → QC). |  |  |  |
| C07 | CST | PT pemasok menyetujui & menyerahkan barang; pergantian pemilik lewat dokumen resmi. Bila beda lokasi: … |  |  |  |
| C08 | Sistem | Roll yang tersedia dicadangkan otomatis ke SO backorder (urutan FIFO). |  |  |  |
| C09 | Admin Sales | Lanjutkan A09–A11 untuk qty yang sudah tersedia; kirim sebagian bila kebijakan kirim sebagian aktif, sisa … |  |  |  |

## D1 — PR → PO supplier atau Order Makloon

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| D01 | Admin Sales | Kebutuhan pembelian lahir dari: kekurangan SO (rencana pemenuhan), Pesanan Khusus (jalur supplier/makloon … |  |  |  |
| D02 | Sistem | PR bernomor; baris membawa produk, qty, unit, gudang terima. |  |  |  |
| D03 | Manajer | ACC atau tolak PR di atas ambang. |  |  |  |
| D04 | Pembelian | Per baris pilih jalur: beli ke supplier atau makloon. Default mengikuti master restock artikel (Master … |  |  |  |
| D05 | Pembelian | Pilih supplier, gudang penerimaan, tanggal kirim; boleh sebagian baris. Hasil: PO KSC/PO-xxxxx dan tugas … |  |  |  |
| D06 | Pembelian | Jalur makloon: mitra, resep proses, output & unit, kebutuhan bahan/greige; reservasi bahan ≠ pengeluaran. … |  |  |  |
| D07 | Manajer | PO ≥ Rp100 jt (bawaan) wajib ACC. |  |  |  |
| D08 | Supplier | Supplier mengirim barang + Surat Jalan supplier (nomor PO tercantum). |  |  |  |
| D08b | Gudang | Makloon: gudang mengeluarkan bahan sesuai dokumen (stock movement keluar tepat sekali), mitra memproses; … |  |  |  |

## D2 — Kedatangan barang, hitung fisik, MD Quality, QC & stok

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| D10 | Admin Gudang | Pilih mitra (supplier / makloon), gudang penerimaan, PO/MKO yang datang. Satu kedatangan = satu SJ satu mitra. |  |  |  |
| D11 | Admin Gudang | Koreksi hasil baca: nomor & tanggal SJ, nama pemasok tercetak, referensi PO; baris barang (qty & unit … |  |  |  |
| D12 | Gudang | Per roll catat fisik: panjang (yard/meter) atau berat (kg), LOT supplier, grade; tempel label. Penerimaan … |  |  |  |
| D13 | Admin Gudang | Sistem menampilkan selisih: kurang vs SJ (toleransi), jumlah roll beda, barang tidak di SJ, melebihi sisa … |  |  |  |
| D14 | Admin Gudang | Posting penerimaan: stok bertambah sebesar fisik; PO menjadi Sebagian diterima bila kurang; sisa PO tetap … |  |  |  |
| D15 | Admin Gudang | Pilih petugas (QC), bagian, tanggal SPK. |  |  |  |
| D16 | MD Quality | Pilih roll yang diuji (sebagian/semua). Bandingkan dengan sample ACC: hasil warna (sesuai / beda shade / … |  |  |  |
| D17 | QC | Isi panjang diinspeksi (selalu yard, walau stok kg) & cacat per interval 15 yd; grade saran dari total poin. |  |  |  |
| D18 | Admin Gudang | Putuskan: terima / terima sebagian / turun grade / tolak → tutup SPK. Barang ditahan → [Lepas tahanan … |  |  |  |
| D19 | QC | Terima qty (grade) dan/atau tolak qty (disposisi: rusak / retur ke supplier → Nota Debit otomatis). |  |  |  |
| D20 | Sistem | Stok tersedia dialokasikan FIFO ke SO backorder (C08); putaway ke rak/bin. |  |  |  |
| D21 | Finance | Tagihan supplier dicocokkan dengan penerimaan (GR belum ditagih), tukar faktur (kontrabon), bayar sesuai … |  |  |  |

## E1 — Pesanan sample: standar, hanger, catalogue; gratis/berbayar

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| E01 | Sales | Pilih jenis: Standar (woven ≤ 5 yd, knit ≤ 2 kg) · Hanger (woven ≤ 0,5 yd) · Catalogue (1 yd tiap warna yang … |  |  |  |
| E02 | Sistem | Nomor KSC/SOS-xxxxx terpisah dari SO; muncul di Penjualan › Pesanan Sample & Meja Sample. |  |  |  |
| E03 | Finance | Pastikan pembayaran/kesepakatan bayar sudah ada, isi catatan, setujui. Admin Sample juga berwenang. |  |  |  |
| E04 | Admin Sample | Teruskan ke gudang; untuk catalogue boleh mengganti warna soft (hanya komponen tambahan, berjejak). |  |  |  |
| E05 | Gudang | Scan roll induk (RFID/QR/nomor), potong, catat panjang aktual. |  |  |  |
| E06 | Admin Sample | Admin Cutting menerima potongan dari gudang (serah terima). |  |  |  |
| E07 | Gudang | SJ sample terbit; kirim (ekspedisi/armada) atau ambil. |  |  |  |
| E08 | Finance | Untuk sample berbayar catat uang masuk atas nilai aktual. |  |  |  |

## F1 — Permintaan custom multi-item, persetujuan & routing

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| F01 | Pelanggan | Kebutuhan produk yang belum ada: motif/artwork, warna (Pantone/labdip), handfeel, qty per produk (bisa >1 … |  |  |  |
| F02 | Sales | Isi pelanggan (pemilik permintaan), judul, kebutuhan umum, tanggal target, catatan pesanan. |  |  |  |
| F03 | Sales | Per item: sumber (induk produk existing untuk custom warna · desain existing yang belum jadi produk · desain … |  |  |  |
| F04 | Sales | Ajukan OD draf ke persetujuan. |  |  |  |
| F05 | Manajer | Rantai persetujuan berjenjang dari matriks persetujuan (Manajer, lalu Direksi bila nilai besar). |  |  |  |
| F06 | Sistem | Routing: printing → Permintaan Desain (DSR) ke Desainer (F2); labdip/handfeel → Permintaan Sample R&D dengan … |  |  |  |

## F2 — Ronde desain, Print paper & ACC PIC

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| F07 | MD | Pilih desainer & tenggat; sumber permintaan (Special Order / pelanggan / internal) terlihat. |  |  |  |
| F08 | Desainer | Kerjakan artwork; unggah versi ronde ini (versi lama tetap bisa dibuka). |  |  |  |
| F09 | Desainer | Print paper = checklist aktivitas cetak kertas per ronde (bukan persetujuan). Serah hasil harus menunjuk … |  |  |  |
| F10 | PIC | Salah satu PIC berwenang meninjau (tidak perlu semua PIC). |  |  |  |
| F11 | PIC | ACC dengan nilai desain (skor, bukan nilai penjualan). Revisi: alasan wajib → kembali ke desainer, ronde +1, … |  |  |  |
| F12 | Sales | Perubahan motif utama bukan revisi artwork yang sama → OD baru berlabel redesign dengan tautan asal. |  |  |  |

## F3 — Sampling R&D, keputusan pelanggan & reproofing

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| F13 | R&D | Periksa spesifikasi (diwarisi dari OD), pilih supplier/mitra peserta & pelaksana fisik sample, jenis uji … |  |  |  |
| F14 | Supplier | Supplier membuat sample labdip/handfeel/proofing dan mengirim. |  |  |  |
| F15 | R&D | Catat kedatangan sample per supplier, siklus/ronde, jenis. |  |  |  |
| F16 | R&D | Nilai per jenis (skor, catatan penilai) → pilih pemenang & keputusan sampling. Satu ACC tidak meluluskan … |  |  |  |
| F17 | Sales | Kirim sample fisik ke pelanggan untuk diputus. |  |  |  |
| F18 | Admin Sales | Catat keputusan pelanggan: ACC / [Minta revisi] / [Tolak] + tanggal, catatan & bukti (foto/WA). |  |  |  |

## F4 — Kunci harga, SKU, pengadaan per item & konversi ke SO

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| F19 | Admin Sales | Harga final per item = harga kontrak supplier pemenang + margin (bawaan 30%, bisa diubah). Acuan awal: harga … |  |  |  |
| F20 | MD | Custom warna dari induk → varian/SKU baru tertaut induk & item yang benar; warna lama tidak ditimpa. SKU … |  |  |  |
| F21 | Pembelian | Per item pilih Supplier (PR → PO) atau Makloon (PR → MKO) sesuai kemampuan produk/master; lanjut di Alur D. |  |  |  |
| F22 | Gudang | Penerimaan aktual menjadi acuan qty (bukan estimasi). |  |  |  |
| F23 | Admin Sales | Konversi ke SO: item A & B, SKU, unit, harga terkunci per item; lanjut Alur A mulai verifikasi (A08). |  |  |  |
| F24 | Sistem | SJ terbit untuk SO hasil OD → OD Dikirim; SO diterima → OD Selesai. |  |  |  |

## G1 — Multi-gudang, konsolidasi transit & leg Jakarta

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| G01 | Gudang | Satu SO berisi woven + knitting + printing → tugas pick terpisah per gudang Rancamalang (Woven / Knitting / … |  |  |  |
| G02 | Gudang | Transfer internal gudang sumber → Rancamalang · Gudang Transit (owner & reservasi tetap); gudang transit … |  |  |  |
| G03 | Admin Gudang | Scan semua roll yang naik kendaraan (handheld C72). |  |  |  |
| G04 | Admin Gudang | Satu armada membawa beberapa SO; SJ tetap per SO per keberangkatan; manifest memuat semua SJ. |  |  |  |
| G05 | Sopir | Perjalanan Rancamalang → Jakarta (bukan pengiriman pelanggan). |  |  |  |
| G06 | Gudang · Jakarta | Scan roll yang turun; bandingkan dengan yang benar-benar diberangkatkan; selisih per roll dicatat. |  |  |  |
| G07 | Gudang · Jakarta | Validasi muatan lagi di Jakarta, terbitkan SJ baru Jakarta → pelanggan dengan referensi SO & SJ transit; … |  |  |  |
| G08 | Sopir | Penerimaan internal Jakarta bukan POD pelanggan. |  |  |  |

## H1 — Pengajuan retur, perjalanan Jakarta → Rancamalang & QC

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| H01 | Pelanggan | Pelanggan mengeluh (warna beda, kotor/noda, sobek/lubang, salah kirim, kurang yard, handfeel). Masa klaim 21 … |  |  |  |
| H02 | Sales | Daftar roll yang benar-benar terkirim (SJ, ID roll, qty, unit) tampil otomatis — tidak bisa tambah produk … |  |  |  |
| H03 | Sistem | Cek: roll milik SO ini, qty ≤ sisa terkirim dikurangi klaim aktif, tenggat 21 hari dari SJ sampai tanggal … |  |  |  |
| H04 | Manajer | Setujui izin barang kembali untuk diperiksa. |  |  |  |
| H05 | Gudang · Jakarta | Terima roll retur di Jakarta; dokumen terima (TRM) per scan. |  |  |  |
| H06 | Gudang · Jakarta | Asal Jakarta, tujuan Rancamalang · Gudang Transit (area QC), kurir/armada. |  |  |  |
| H07 | Gudang · Rancamalang | Cocokkan roll dengan pengiriman sebelumnya. |  |  |  |
| H08 | QC | Per roll: qty aktual hasil ukur, kondisi, cacat 4-point, grade, catatan. Potongan baik dari roll retur … |  |  |  |

## H2 — Cutloss, kompensasi, keputusan akhir, disposisi & pengganti

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| H09 | MD Quality | Saat QC: catat qty cacat dalam yard (bukan kelipatan 15; produk kg dikonversi otomatis) + posisi cacat … |  |  |  |
| H09b | MD Quality | Roll dipecah fisik: potongan baik → dikirim kembali dengan SJ baru merujuk SJ & SO asal; potongan cacat → BS … |  |  |  |
| H10 | Finance | Nilai = harga transaksi awal (neto setelah diskon/harga khusus) × qty disetujui (KLR-02); diskon = nominal … |  |  |  |
| H11 | Manajer | Pilih outcome Refund · Store credit (potong bon) · Nego (diskon/cutloss) · Tukar · Tolak; boleh per … |  |  |  |
| H12 | Finance | SO asal belum lunas → nilai mengurangi tagihan dulu, sisa → refund atau saldo. SO asal sudah lunas → … |  |  |  |
| H13 | Admin Sales | SO pengganti tertaut retur: artikel/warna/grade sama; qty dalam yard aktual hasil QC (KLR-03); menunggu … |  |  |  |
| H14 | Admin Sales · pemilik Sukacita | Sukacita memilih simpan (owner tetap, grade/hold mengikuti QC — bukan otomatis tersedia) atau kembalikan ke … |  |  |  |
| H15 | CST | CST wajib menerima retur internal; owner berpindah lewat dokumen; fisik tetap di gudang shared (tanpa … |  |  |  |
| H16 | CST | CST memilih simpan sebagai stok atau buang (BS) dengan bukti, atau retur ke supplier (H17). |  |  |  |
| H17 | Admin Gudang · CST | Retur beli merujuk PO, penerimaan (GRN), roll & asal SO/SJ/retur pelanggan. Tenggat supplier 21 hari sampai … |  |  |  |

## I1 — Termin, faktur pajak, kwitansi, selisih sampai LUNAS

| Langkah | Peran | Ringkasan | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|
| I01 | Sales | Termin dipilih saat SO: Tunai · CBD — Bayar Sebelum Kirim · DP 50% + Pelunasan · NET 7/14/30/60/90 · … |  |  |  |
| I02 | Finance | CBD/DP: catat pembayaran sebelum barang keluar (uang muka; kewajiban sampai dikirim). |  |  |  |
| I03 | Finance | PT PKP: isi kode transaksi (04), tanggal faktur; NSFP 16 digit menyusul dari Coretax ([Cetak Faktur Pajak]). |  |  |  |
| I04 | Admin Sales | Cetak Faktur Komersial (invoice) & SJ dari Pusat Dokumen › Cetak PDF & Label; kirim ke pelanggan. |  |  |  |
| I05 | Admin Sales | Ingatkan pelanggan sebelum/sesudah jatuh tempo. Sales yang menerima kabar sudah transfer melapor lewat Kasus … |  |  |  |
| I06 | Finance | Isi Jumlah Diterima, Metode (Tunai → Kas Kecil; Transfer Bank/Giro/QRIS → Bank), tanggal, no. referensi; … |  |  |  |
| I07 | Finance | Lebih bayar: simpan deposit / refund / alokasi ke SO lain / write-off kecil (pembulatan). Kurang bayar: sisa … |  |  |  |
| I08 | Finance | Nota denda keterlambatan hasil hitungan sistem diterbitkan Finance; pembebasan denda → manajer. Pantau umur … |  |  |  |
| I09 | Manajer | Void membalik pembayaran di SO, kas & deposit; tercatat di audit. |  |  |  |
| I10 | Sistem | SO Lunas: piutang 0; Perjalanan Pesanan menampilkan Dikirim · Diterima · Ditagih · Dibayar. |  |  |  |

## J — Akses per peran

| ID | Peran | Uji | Status | Catatan |
|---|---|---|---|---|
| J01 | Sales | positif & negatif akses |  |  |
| J02 | Admin Sales | positif & negatif akses |  |  |
| J03 | Manajer / PIC | positif & negatif akses |  |  |
| J04 | Finance | positif & negatif akses |  |  |
| J05 | Gudang | positif & negatif akses |  |  |
| J06 | Admin Gudang | positif & negatif akses |  |  |
| J07 | Sopir | positif & negatif akses |  |  |
| J08 | QC | positif & negatif akses |  |  |
| J09 | MD Quality | positif & negatif akses |  |  |
| J10 | MD / R&D | positif & negatif akses |  |  |
| J11 | Desainer | positif & negatif akses |  |  |
| J12 | Admin Sample | positif & negatif akses |  |  |
| J13 | Role kustom & view-only | positif & negatif akses |  |  |

## K — Konsistensi data

| ID | Pemeriksaan | Status | Catatan |
|---|---|---|---|
| K01 | Meja vs daftar vs detail |  |  |
| K02 | Perjalanan Pesanan |  |  |
| K03 | Qty & nilai berantai |  |  |
| K04 | Satuan |  |  |
| K05 | Pesanan Khusus → SO |  |  |
| K06 | Sample |  |  |
| K07 | Retur |  |  |
| K08 | Laporan & Pusat Export |  |  |
| K09 | Ketahanan layar |  |  |

## Form satu temuan

| Field | Isi |
|---|---|
| ID temuan / langkah |  |
| Akun / peran / badan usaha |  |
| Dokumen / roll |  |
| Langkah reproduksi |  |
| Seharusnya |  |
| Yang terjadi / dampak |  |
| Bug / keputusan bisnis / data |  |
| Prioritas / PIC / target |  |
| Commit perbaikan / retest |  |

## Penutupan

- Lulus ___ · Gagal ___ · Terblokir ___ · Tidak diuji ___
- Alur dinyatakan siap pakai: ___
- Keputusan bisnis yang diambil: ___
- Rencana perbaikan & tanggal uji ulang: ___
- Tanda tangan: pemilik proses ___ · Production IT ___ · fasilitator ___ · pencatat ___
