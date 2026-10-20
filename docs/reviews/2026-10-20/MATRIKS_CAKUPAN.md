# Matriks pelacakan audit — belum sign-off

Acuan: `63c38bd11b49ddfb59cbbfdb915c2e11e16d5c9c`.

Inventaris mencakup seluruh 56 requirement dan 230 acceptance plan. **Terdaftar tidak berarti teruji.** Tidak ada PASS yang diberikan hanya karena nama tes atau dokumen developer cocok. Butir tanpa pembuktian penuh tetap BELUM VALIDASI PENUH. Temuan tambahan di luar skenario acceptance ada pada TEMUAN_TERVERIFIKASI.md.

## L00 — Baseline, penyelarasan keputusan, dan kontrak perubahan

Baseline dan inventaris tersedia. Dataset migrasi KN asli belum direkonstruksi; fixture spesifik MKO tidak tersedia.

### LN-001 — Baseline aktual dan rekonsiliasi fase lama

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-001-T01 | BELUM VALIDASI PENUH | Diberikan repo target, ketika preflight dijalankan, maka SHA/branch/delta dan lingkungan uji tercatat, tanpa mereset pekerjaan lain. **Catatan:** Baseline dan inventaris tersedia. Dataset migrasi KN asli belum direkonstruksi; fixture spesifik MKO tidak tersedia. |
| LN-001-T02 | BELUM VALIDASI PENUH | Diberikan status P05 implemented_pending_validation dan P06–P10 not_started, ketika tracker dipetakan, maka tidak ada klaim semuanya sudah tervalidasi; setiap ACC lama mempunyai disposisi dipertahankan, diuji ulang, diganti, atau pending dengan alasan. **Catatan:** Baseline dan inventaris tersedia. Dataset migrasi KN asli belum direkonstruksi; fixture spesifik MKO tidak tersedia. |

### LN-002 — Kontrak perubahan dan keputusan belum final

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-002-T01 | BELUM VALIDASI PENUH | Diberikan keputusan yang bertentangan, ketika kontrak aktif dibuat, maka keputusan owner terbaru menang dan catatan historis tetap terbaca. **Catatan:** Baseline dan inventaris tersedia. Dataset migrasi KN asli belum direkonstruksi; fixture spesifik MKO tidak tersedia. |
| LN-002-T02 | BELUM VALIDASI PENUH | Diberikan KLR-01 atau KLX-02 belum dijawab, ketika agent mengerjakan bagian independen, maka tidak ada formula cutloss atau rumus grade baru yang diaktifkan; kebutuhan dependennya tercatat blocked_by_decision. **Catatan:** Baseline dan inventaris tersedia. Dataset migrasi KN asli belum direkonstruksi; fixture spesifik MKO tidak tersedia. |

### LN-003 — Fixture, risiko migrasi, dan rencana bukti

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-003-T01 | BELUM VALIDASI PENUH | Diberikan fixture, ketika baseline dihitung, maka stok per owner/lokasi/satuan, komitmen, AR/AP dan identitas roll memiliki angka pembanding yang tersimpan. **Catatan:** Baseline dan inventaris tersedia. Dataset migrasi KN asli belum direkonstruksi; fixture spesifik MKO tidak tersedia. |
| LN-003-T02 | BELUM VALIDASI PENUH | Diberikan rencana migrasi, ketika dry-run pada salinan data dilakukan, maka record yatim, duplikat dan saldo tidak seimbang dilaporkan; data produksi tidak diubah. **Catatan:** Baseline dan inventaris tersedia. Dataset migrasi KN asli belum direkonstruksi; fixture spesifik MKO tidak tersedia. |

## L01 — Custom role, master data, grade, dan konfigurasi visibilitas

Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh.

### LN-010 — Editor hak akses empat tingkat dan enforcement

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-010-T01 | BELUM VALIDASI PENUH | Diberikan custom role baru, ketika satu aktivitas diizinkan dan lainnya ditolak, maka layar, API langsung, detail dan export mengikuti izin efektif yang sama. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |
| LN-010-T02 | BELUM VALIDASI PENUH | Diberikan dua PIC berwenang menekan ACC bersamaan, ketika satu berhasil, maka hanya satu transisi/efek berikutnya tercatat dan PIC lainnya melihat keputusan yang telah selesai. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |
| LN-010-T03 | BELUM VALIDASI PENUH | Diberikan admin Jakarta, ketika meminta data aktivitas Bandung tanpa scope, maka API menolak atau menyaring data tanpa membocorkan hitungan. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |

### LN-011 — Stage, jenis kain, supplier/color dan master lifecycle

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-011-T01 | BELUM VALIDASI PENUH | Diberikan satu woven PFD dan satu woven finished dengan supplier color berbeda, ketika dicari/filter/detail, maka tahap dan jenis tidak tertukar serta seluruh kode sumber dapat ditelusuri. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |
| LN-011-T02 | BELUM VALIDASI PENUH | Diberikan SKU dipakai SO/roll, ketika dinonaktifkan, maka transaksi baru dibatasi sesuai kebijakan dan histori tetap terbuka; hard delete tidak menghapus referensi. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |
| LN-011-T03 | BELUM VALIDASI PENUH | Diberikan SKU bahan dan SKU lahir dari MD, ketika dibuat, maka jalur uji sesuai asal/lini dan tidak membuat SKU kedua pada revalidation. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |

### LN-012 — Grade dinamis, rank customer dan konfigurasi POS

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-012-T01 | BELUM VALIDASI PENUH | Diberikan minimum customer B, ketika alokasi A dipilih, maka diterima; minimum A dengan alokasi B ditolak kecuali mekanisme pengecualian yang memang disetujui secara eksplisit. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |
| LN-012-T02 | BELUM VALIDASI PENUH | Diberikan Sales saat trial, ketika membuka katalog, SO, detail dan export, maka grade tidak bocor; Admin Sales berwenang dapat melihatnya. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |
| LN-012-T03 | BELUM VALIDASI PENUH | Diberikan admin menambah grade baru, ketika rank dan harga ditetapkan, maka alokasi/filter berjalan tanpa perubahan kode dan transaksi grade lama tetap terbaca. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |
| LN-012-T04 | BELUM VALIDASI PENUH | Diberikan PFD/PFP dan greige, ketika Sales berizin membuka daftar bahan jual, maka PFD/PFP tersedia sesuai konfigurasi, sedangkan greige tidak dapat dipesan melalui API langsung. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |
| LN-012-T05 | BELUM VALIDASI PENUH | Diberikan Sales dengan konfigurasi default, ketika membuka katalog/detail/facet/export, maka LOT dan asal lokal/impor tidak terlihat. Mengubah konfigurasi atribut itu hanya oleh role berwenang; grade tetap tidak terbuka bagi Sales termasuk trial. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |

### LN-013 — Default restock dan konteks entitas MD

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-013-T01 | BELUM VALIDASI PENUH | Diberikan artikel default makloon, ketika user berizin memilih pembelian supplier secara manual, maka default tidak menjadi hard block dan alasan/pilihan tercatat. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |
| LN-013-T02 | BELUM VALIDASI PENUH | Diberikan MD mengelola dua entitas, ketika membuat PO, maka entitas buyer, owner hasil penerimaan dan AP eksplisit serta konsisten; perubahan tampilan tidak memindahkan saldo. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |

### LN-014 — LOT supplier dan identitas LOT internal

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-014-T01 | BELUM VALIDASI PENUH | Diberikan lot internal dengan supplier_lot 234, ketika receiving/detail/label/retur ditelusuri, maka dua identitas tetap dibedakan dan PO/SJ asal dapat ditemukan. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |
| LN-014-T02 | BELUM VALIDASI PENUH | Diberikan perubahan metadata LOT berizin, ketika disimpan, maka ID canonical dan hubungan roll/stock/inspection historis tidak berubah; auto-alias hanya diaktifkan setelah aturan KLX-01 disetujui. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |

### LN-015 — Detail UI/UX dan otorisasi custom role lintas modul

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-015-T01 | BELUM VALIDASI PENUH | Inventaris seluruh menu/tab/aktivitas seluruh fase: tiap aksi mempunyai permission ID stabil, label manusia, scope, field policy, route/service enforcement dan test. Tidak ada aksi baru yang hanya mengikuti nama staf/role hardcoded atau izin manage generik tanpa pemetaan. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |
| LN-015-T02 | BELUM VALIDASI PENUH | Editor Modul > Menu > Submenu/Tab > Aktivitas menunjukkan checked/unchecked/partial yang benar. Pilih semua, cari dan filter tidak mengubah izin tersembunyi tanpa ringkasan; preset tidak menghapus pilihan detail tanpa konfirmasi diff. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |
| LN-015-T03 | BELUM VALIDASI PENUH | PIC Proofing boleh menilai proofing tetapi tidak labdip/handfeel, kontrak atau pembayaran. Uji melalui UI dan API langsung, bulk, deep link dan export. Mengganti nama role tidak mengubah izin efektif. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |
| LN-015-T04 | BELUM VALIDASI PENUH | Preview role pada entitas/lokasi/lini yang dipilih sama dengan izin aktual server, termasuk asal izin dan alasan penolakan. Grant role yang sama tidak memperluas scope akun; agregasi/list/detail/export tidak membocorkan data di luar scope. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |
| LN-015-T05 | BELUM VALIDASI PENUH | Satu anggota PIC berwenang dapat ACC tanpa menunggu anggota lain; dua ACC serentak menghasilkan satu keputusan. Hak input hasil, ACC teknis, tindak lanjut hasil gagal, release master, kontrak dan realisasi pengadaan diuji terpisah. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |
| LN-015-T06 | BELUM VALIDASI PENUH | Perubahan hak saat halaman dan session masih terbuka berlaku pada request berikutnya melalui invalidasi/version check. User tidak dapat mengubah role/grant sendiri tanpa hak delegasi; delegasi tidak melampaui batas pemberi sesuai kebijakan yang didokumentasikan. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |
| LN-015-T07 | BELUM VALIDASI PENUH | Migrasi role existing mempunyai mapping sebelum/sesudah dan akun terdampak; tidak memberi semua aktivitas baru secara otomatis karena preset manage lama. Role custom, peran terkunci dan izin lama tetap dapat direkonsiliasi; tidak ada silent privilege expansion. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |
| LN-015-T08 | BELUM VALIDASI PENUH | UAT editor di desktop dan lebar tablet: label aktivitas terbaca, keyboard/fokus berfungsi, panel detail dan pencarian dapat dipakai, perubahan belum disimpan diperingatkan, diff dan pengguna terdampak jelas. Error simpan tidak menghilangkan pilihan; bukti berupa layar dan langkah pengguna. **Catatan:** Tes custom role dan sejumlah proteksi field berjalan. Data SKU impor/grade historis belum lengkap; UI empat tingkat belum ditelusuri menyeluruh. |

## L02 — Penjualan, alokasi roll, harga khusus dan konsistensi Finance

Tes ATP/alokasi, special price dan beberapa permukaan AR lulus. Belum sign-off seluruh rekonsiliasi AR/AP/interco dan skenario gangguan.

### LN-020 — ATP, Keep/Pending dan satuan pada SO

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-020-T01 | BELUM VALIDASI PENUH | Diberikan 100 yard stok fisik seluruhnya layak jual, 30 yard sudah reserved dan 20 yard incoming yang belum diterima, ketika dashboard/checkout dihitung, maka on-hand 100, reserved 30, free physical 70 dan incoming 20 ditampilkan terpisah; 20 incoming tidak dianggap siap kirim. Jika ada angka available-to-order berbasis forecast, sumber, komitmen dan definisinya ditampilkan tanpa menghitung incoming dua kali. **Catatan:** Tes ATP/alokasi, special price dan beberapa permukaan AR lulus. Belum sign-off seluruh rekonsiliasi AR/AP/interco dan skenario gangguan. |
| LN-020-T02 | BELUM VALIDASI PENUH | Diberikan pending tiga produk pada dua dokumen pemenuhan, ketika Sales membuka antrean, maka dapat menelusuri produk, qty pending, ETA yang tersedia dan dokumen sumber tanpa melihat owner tersembunyi. **Catatan:** Tes ATP/alokasi, special price dan beberapa permukaan AR lulus. Belum sign-off seluruh rekonsiliasi AR/AP/interco dan skenario gangguan. |
| LN-020-T03 | BELUM VALIDASI PENUH | Diberikan SO yard dan SO kg, ketika dibuka pada list/detail/print, maka jumlah roll dan qty per identitas terlihat dengan satuan benar; tidak ada penjumlahan yard dengan kg. **Catatan:** Tes ATP/alokasi, special price dan beberapa permukaan AR lulus. Belum sign-off seluruh rekonsiliasi AR/AP/interco dan skenario gangguan. |

### LN-021 — Roll picker dan perubahan alokasi yang sah

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-021-T01 | BELUM VALIDASI PENUH | Diberikan sembilan roll 100 yard dan satu roll 105 yard, ketika checkout 1000 yard, maka pilihan atas 1005/10 roll dan bawah 905/9 roll konsisten hingga detail SO. **Catatan:** Tes ATP/alokasi, special price dan beberapa permukaan AR lulus. Belum sign-off seluruh rekonsiliasi AR/AP/interco dan skenario gangguan. |
| LN-021-T02 | BELUM VALIDASI PENUH | Diberikan dua SO bersamaan mengincar roll sama, ketika alokasi disimpan, maka hanya satu reservation sah; perubahan gagal tidak melepas reservation lama tanpa pengganti. **Catatan:** Tes ATP/alokasi, special price dan beberapa permukaan AR lulus. Belum sign-off seluruh rekonsiliasi AR/AP/interco dan skenario gangguan. |
| LN-021-T03 | BELUM VALIDASI PENUH | Diberikan Admin Sales mengganti roll sebelum picking, ketika SO dihitung ulang, maka qty, harga dan dokumen downstream mengacu versi alokasi terbaru; dispatch lama dibatalkan atau direvalidasi sesuai alur. **Catatan:** Tes ATP/alokasi, special price dan beberapa permukaan AR lulus. Belum sign-off seluruh rekonsiliasi AR/AP/interco dan skenario gangguan. |

### LN-022 — Harga grade dan pengajuan ulang Special Price

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-022-T01 | BELUM VALIDASI PENUH | Diberikan perubahan alokasi dan request harga kedua, ketika approver menyetujui versi baru, maka nominal final memakai request terbaru yang tepat dan versi lama tidak dapat menimpa. **Catatan:** Tes ATP/alokasi, special price dan beberapa permukaan AR lulus. Belum sign-off seluruh rekonsiliasi AR/AP/interco dan skenario gangguan. |
| LN-022-T02 | BELUM VALIDASI PENUH | Diberikan urutan item SO berubah saat approval pending, ketika ACC diterima, maka harga tidak tertempel pada produk berbeda. **Catatan:** Tes ATP/alokasi, special price dan beberapa permukaan AR lulus. Belum sign-off seluruh rekonsiliasi AR/AP/interco dan skenario gangguan. |
| LN-022-T03 | BELUM VALIDASI PENUH | Diberikan invoice telah diposting, ketika ada perubahan transaksi yang sah, maka melalui dokumen koreksi/amandemen dan jejak jurnal, bukan edit histori atau posting dobel. **Catatan:** Tes ATP/alokasi, special price dan beberapa permukaan AR lulus. Belum sign-off seluruh rekonsiliasi AR/AP/interco dan skenario gangguan. |

### LN-023 — AR, AP, revisi PO dan dampak finansial

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-023-T01 | BELUM VALIDASI PENUH | Diberikan SO tempo confirmed belum dikirim, kemudian sebagian dikirim dan dibayar sebagian, ketika list SO/AR aging/GL/report dibandingkan, maka angka dan label definisinya cocok pada setiap tahap; exposure tidak dijumlah lagi sebagai AR ledger. **Catatan:** Tes ATP/alokasi, special price dan beberapa permukaan AR lulus. Belum sign-off seluruh rekonsiliasi AR/AP/interco dan skenario gangguan. |
| LN-023-T02 | BELUM VALIDASI PENUH | Diberikan order 1000 dan receipt 960, ketika ditutup sesuai keputusan, maka sisa order, AP/invoice dan kelebihan pembayaran mempunyai tindak lanjut eksplisit dan rekonsiliasi yang seimbang. **Catatan:** Tes ATP/alokasi, special price dan beberapa permukaan AR lulus. Belum sign-off seluruh rekonsiliasi AR/AP/interco dan skenario gangguan. |
| LN-023-T03 | BELUM VALIDASI PENUH | Diberikan retry close/post/payment, ketika request diulang, maka jurnal, alokasi pembayaran dan saldo hanya berubah sekali. **Catatan:** Tes ATP/alokasi, special price dan beberapa permukaan AR lulus. Belum sign-off seluruh rekonsiliasi AR/AP/interco dan skenario gangguan. |

### LN-024 — Utang/piutang interco dan pembayaran per transaksi

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-024-T01 | BELUM VALIDASI PENUH | Diberikan Sukacita membeli dari CST, ketika barang diterima sebelum pembayaran, maka stock owner dan pasangan AR/AP sah tanpa harus menunggu kas; saldo masing-masing entitas tidak digabung. **Catatan:** Tes ATP/alokasi, special price dan beberapa permukaan AR lulus. Belum sign-off seluruh rekonsiliasi AR/AP/interco dan skenario gangguan. |
| LN-024-T02 | BELUM VALIDASI PENUH | Diberikan dua invoice berlawanan arah, ketika dibayar, maka masing-masing transaksi dibayar penuh dan referensi pembayaran/jurnal jelas, tanpa netting otomatis. **Catatan:** Tes ATP/alokasi, special price dan beberapa permukaan AR lulus. Belum sign-off seluruh rekonsiliasi AR/AP/interco dan skenario gangguan. |
| LN-024-T03 | BELUM VALIDASI PENUH | Diberikan cutoff belum diputuskan, ketika daftar aging/jadwal pembayaran disiapkan, maka tanggal tidak diasumsikan sendiri; setelah KLX-03 diputuskan, transaksi sebelum/sesudah cutoff masuk periode yang benar. **Catatan:** Tes ATP/alokasi, special price dan beberapa permukaan AR lulus. Belum sign-off seluruh rekonsiliasi AR/AP/interco dan skenario gangguan. |

## L03 — Special Order, Designer, uji kain dan rute supplier/makloon

18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap.

### LN-030 — Sumber desain, multi-produk dan status HOLD

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-030-T01 | BELUM VALIDASI PENUH | Diberikan satu request dua produk dari sumber berbeda, ketika disimpan dan ditindaklanjuti, maka dokumen desain/proofing/qty tetap terkait item yang benar. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-030-T02 | BELUM VALIDASI PENUH | Diberikan artwork ACC tanpa master produk, ketika dipilih, maka dapat dipakai tanpa membuat produk fiktif; artwork HOLD tidak aktif sebelum PIC melepasnya. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-030-T03 | BELUM VALIDASI PENUH | Diberikan perubahan motif dari artwork lama, ketika diajukan, maka membuat Special Order baru berlabel redesign dengan tautan asal, bukan mengaburkan revisi proofing request lama. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |

### LN-031 — Round designer dan persetujuan yang sudah ada

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-031-T01 | BELUM VALIDASI PENUH | Diberikan beberapa round desain, ketika print paper dicentang, maka tercatat round, pelaku dan waktu, tanpa otomatis menyetujui desain/proofing. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-031-T02 | BELUM VALIDASI PENUH | Diberikan satu PIC melakukan ACC, ketika handler selesai, maka tahap berikutnya muncul sekali dan status pengguna lain langsung sesuai; ACC customer oleh Sales tetap jelas objek dan buktinya. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |

### LN-032 — Uji kain sesuai lini dan proofing printing berulang

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-032-T01 | BELUM VALIDASI PENUH | Diberikan Special Order printing dari produk/artwork existing, ketika desain selesai, maka task proofing dibuat dan tidak langsung produksi hanya karena desain ACC. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-032-T02 | BELUM VALIDASI PENUH | Diberikan customer menolak proofing printing dua kali lalu ACC, ketika Sales mencatat keputusan, maka tiga round tersimpan dengan artwork sama. Produksi/SKU akhir hanya lanjut setelah seluruh uji relevan termasuk handfeel bila diwajibkan, spesifikasi dan ACC final terpenuhi, dengan efek tepat satu kali. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-032-T03 | BELUM VALIDASI PENUH | Diberikan dua request revalidation existing SKU serentak, ketika keduanya mencapai final, maka tidak lahir SKU/spec duplikat atau dua proses aktif yang melanggar aturan existing. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-032-T04 | BELUM VALIDASI PENUH | Diberikan Special Order polos dengan labdip dan handfeel sesuai lini, ketika diproses dan revisi, maka jenis uji tetap sesuai konfigurasi, tanpa task proofing printing otomatis atau keharusan checklist paper pada jalur tanpa desain. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |

### LN-033 — Rute pemenuhan supplier/makloon dari R&D dan Pesanan Khusus

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-033-T01 | BELUM VALIDASI PENUH | Rilis R&D dengan uji wajib belum ACC ditolak tanpa mengubah lifecycle; error tidak ditangani dengan fallback update lifecycle langsung. Setelah semua syarat sah, rilis hanya mengaktifkan produk, tidak otomatis membuat PO/MKO atau mengurangi bahan. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-033-T02 | BELUM VALIDASI PENUH | Pesanan Khusus printing dan polos masing-masing mengikuti proofing atau labdip/handfeel yang relevan; memilih supplier atau makloon tidak melewati persetujuan yang diwajibkan. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-033-T03 | BELUM VALIDASI PENUH | Satu Pesanan Khusus berisi dua item: satu supplier, satu makloon. Pilihan per item tersimpan dan PR/PO/MKO tertaut ke item yang tepat. Default sumber master dapat diubah user berwenang dengan jejak audit; kebijakan both tidak menggagalkan proses karena field alasan hilang. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-033-T04 | BELUM VALIDASI PENUH | Jalur supplier membuat PR purchase dan PO dengan produk, qty, unit, supplier, entitas dan harga pengadaan yang benar; tidak membuat MKO atau mengeluarkan greige milik perusahaan. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-033-T05 | BELUM VALIDASI PENUH | Jalur makloon membuat PR makloon dan MKO untuk produk hasil yang benar; qty/yield forecast, bahan, partner dan biaya jasa tidak diperlakukan sebagai pembelian kain jadi. Tidak membuat PO finished goods palsu agar layar pengiriman terbuka. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-033-T06 | BELUM VALIDASI PENUH | Bahan kurang atau telah direservasi pesanan lain: permintaan tetap terlacak sebagai menunggu bahan; tidak ada reservasi ganda/stock negatif. Rilis produk tidak mengurangi fisik; reservasi dan issue hanya melalui peristiwa existing yang sah. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-033-T07 | TEMUAN TERBUKTI | Klik ulang, dua user bersamaan, timeout setelah PR/PO/MKO berhasil dan retry menghasilkan satu realisasi untuk kebutuhan yang sama; dokumen yang sudah lahir ditemukan kembali. Error terbuka di UI dan tidak menandai pengadaan sukses palsu. **Catatan:** AUD-SO-01: pemegang lease lama menghapus lease baru; duplikasi dokumen belum direproduksi. |
| LN-033-T08 | BELUM VALIDASI PENUH | Pergantian jalur setelah dokumen pengadaan aktif memerlukan pembatalan/amandemen yang sah. Jika bahan sudah di-issue, diperlukan rekonsiliasi/return sesuai flow material; relasi lama tetap auditable tanpa menghapus histori atau menduplikasi supply. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-033-T09 | BELUM VALIDASI PENUH | Hak memilih jalur, mengubah default, merealisasi PR dan membatalkan dokumen diperiksa backend sesuai custom role dan entitas. Memanipulasi request tidak melewati pembatasan atau membuka harga/grade kepada Sales tanpa hak. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-033-T10 | TEMUAN TERBUKTI | Migrasi legacy linked_po_id mempertahankan relasi supplier tanpa membuat ulang dokumen atau posting; data multi-item ambigu ditandai untuk rekonsiliasi, bukan ditebak. Rollback tidak menghapus transaksi yang telah terjadi. **Catatan:** AUD-MIG-01/AUD-MIG-02: apply fulfillment kosong tidak ditulis; rollback menghapus perubahan pascamigrasi. |

### LN-034 — Revalidasi produk per supplier, kontrak terpisah dan keputusan PIC

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-034-T01 | TEMUAN TERBUKTI | Produk existing dapat dipilih untuk labdip, proofing dan handfeel sesuai lini. Proofing menggunakan artwork/versi existing yang disetujui; tidak membuat SKU/spec/desain baru otomatis dan tidak mengubah identitas artikel. **Catatan:** AUD-RND-02: versi artwork tidak ada diterima. |
| LN-034-T02 | BELUM VALIDASI PENUH | Artikel yang lulus supplier A diuji pada B: hasil B tersimpan terpisah dan tidak dianggap lulus karena hasil A. Dua siklus supplier berbeda dapat ditelusuri; retry request sama tidak membuat duplikat. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-034-T03 | BELUM VALIDASI PENUH | Supplier A diuji ulang setelah siklus terdahulu selesai: round baru memiliki referensi acuan dan histori lama utuh. Tampilan mampu membedakan hasil terbaru, hasil terdahulu dan siklus belum selesai; tidak menjadikan satu rnd_supplier sebagai seluruh daftar kelayakan. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-034-T04 | BELUM VALIDASI PENUH | Keputusan teknis ulang dapat selesai tanpa harga baru dan tanpa membuat/mengubah kontrak. Bila kontrak existing direferensikan, validasi produk/supplier/entitas/jenis kontrak dan simpan referensi; harga, masa berlaku dan isi kontrak tetap. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-034-T05 | BELUM VALIDASI PENUH | Pembuatan atau amandemen kontrak hanya lewat aksi komersial terpisah dan berizin; hasil uji makloon tidak otomatis membuat kontrak purchase barang jadi. Retry keputusan tidak menggandakan kontrak/supplier item. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-034-T06 | BELUM VALIDASI PENUH | Hasil uji gagal masuk Menunggu keputusan PIC. Tidak otomatis memblok seluruh produksi, menonaktifkan produk, membatalkan stok/kontrak, atau mengubah hasil gagal menjadi ACC. PIC mencatat tindak lanjut dan cakupan dokumen/supplier; tindakan lanjutan memakai izin serta guard existing. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |
| LN-034-T07 | TEMUAN TERBUKTI | Tanpa keputusan PIC, siklus gagal tidak ditampilkan sebagai kelayakan baru yang lulus. Pekerjaan existing tidak otomatis dihentikan. Tindakan override bila tersedia harus eksplisit, beralasan, berizin dan tetap menyimpan hasil gagal. **Catatan:** AUD-RND-01: labdip ACC dan handfeel ditolak dapat menjadi pass. |
| LN-034-T08 | BELUM VALIDASI PENUH | E2E revalidation -> keputusan PIC -> pengadaan supplier atau makloon LN-033 memakai referensi hasil per produk/supplier/versi yang benar. L14 menguji kontrak existing tidak berubah, tidak ada SKU ganda, serta histori, permission dan keputusan tetap konsisten. **Catatan:** 18 kasus realisasi fulfillment lulus dengan fixture hasil R&D/harga terkunci; dry-run migrasi berhasil secara langsung. Ada cacat revalidation, lease dan migrasi. Rantai sejak R&D sampai Finance/pengiriman belum lengkap. |

## L04 — Receiving, RFID identity, MD Quality, UOM dan material makloon

Pemotongan MD Quality dan beberapa guard berjalan. OCR nyata butuh kredensial layanan; rantai material ledger masih membutuhkan data MKO.

### LN-040 — Receiving aktual dan OCR per roll

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-040-T01 | BELUM VALIDASI PENUH | Diberikan order sepuluh roll 100 yard dan SJ/fisik total 960 dengan variasi panjang, ketika OCR lalu user koreksi dan commit, maka tersimpan sepuluh identitas beserta qty masing-masing dan total 960; confidence rendah ditandai untuk verifikasi. **Catatan:** Pemotongan MD Quality dan beberapa guard berjalan. OCR nyata butuh kredensial layanan; rantai material ledger masih membutuhkan data MKO. |
| LN-040-T02 | BELUM VALIDASI PENUH | Diberikan request receiving sama dikirim ulang, ketika diproses, maka roll/stok/notifikasi tidak dibuat dua kali dan selisih 40 tetap terlihat. **Catatan:** Pemotongan MD Quality dan beberapa guard berjalan. OCR nyata butuh kredensial layanan; rantai material ledger masih membutuhkan data MKO. |

### LN-041 — MD Quality memilih roll dan mencatat dua indikator

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-041-T01 | BELUM VALIDASI PENUH | Diberikan receiving tiga LOT, ketika MDQ memilih dua roll dari LOT berbeda, maka hanya roll terpilih menjadi sumber pengujian dan konsumsi; receiving bruto seluruh roll tidak berubah. **Catatan:** Pemotongan MD Quality dan beberapa guard berjalan. OCR nyata butuh kredensial layanan; rantai material ledger masih membutuhkan data MKO. |
| LN-041-T02 | BELUM VALIDASI PENUH | Diberikan warna tidak sesuai namun keputusan manusia menerima, ketika dicatat dengan hak yang tepat, maka hasil uji dan keputusan akhir terpisah serta dapat diaudit tanpa engine keputusan otomatis. **Catatan:** Pemotongan MD Quality dan beberapa guard berjalan. OCR nyata butuh kredensial layanan; rantai material ledger masih membutuhkan data MKO. |

### LN-042 — Pemotongan 0,25 yard, identitas tag dan konversi kg

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-042-T01 | BELUM VALIDASI PENUH | Diberikan receipt 100 yard dan potong MDQ 0,25 yard, ketika pemakaian diposting ulang/retry, maka receipt tetap 100, saldo 99,75, pemakaian tepat 0,25 sekali, EPC/roll tetap sama. **Catatan:** Pemotongan MD Quality dan beberapa guard berjalan. OCR nyata butuh kredensial layanan; rantai material ledger masih membutuhkan data MKO. |
| LN-042-T02 | BELUM VALIDASI PENUH | Diberikan roll basis kg dan potong 0,25 yard, ketika aturan konversi tersedia, maka kg berkurang sesuai aturan/berat aktual yang tercatat; bila belum ada, transaksi diblok dengan alasan jelas dan bukan mengurangi 0,25 kg otomatis. **Catatan:** Pemotongan MD Quality dan beberapa guard berjalan. OCR nyata butuh kredensial layanan; rantai material ledger masih membutuhkan data MKO. |
| LN-042-T03 | BELUM VALIDASI PENUH | Diberikan label lama 100 dan saldo 99,75, ketika reprint label diperintahkan, maka EPC sama, teks qty terkini dan histori cetak jelas; read RFID mengambil saldo dari ERP. **Catatan:** Pemotongan MD Quality dan beberapa guard berjalan. OCR nyata butuh kredensial layanan; rantai material ledger masih membutuhkan data MKO. |

### LN-043 — Komitmen greige, issue, hasil fisik dan sisa bahan makloon

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-043-T01 | BELUM VALIDASI PENUH | Diberikan bahan 1000 dan kebutuhan produksi 600, ketika komitmen dibuat lalu sebagian di-issue, maka reserved/available dan fisik berubah pada peristiwa yang benar serta antarmuka menjelaskan jumlahnya. **Catatan:** Pemotongan MD Quality dan beberapa guard berjalan. OCR nyata butuh kredensial layanan; rantai material ledger masih membutuhkan data MKO. |
| LN-043-T02 | BELUM VALIDASI PENUH | Diberikan MKO dibatalkan setelah issue, ketika bahan belum kembali, maka stok gudang tidak bertambah otomatis; saat sebagian kembali dan sisanya loss/masih partner, ketiga saldo tetap dapat direkonsiliasi. **Catatan:** Pemotongan MD Quality dan beberapa guard berjalan. OCR nyata butuh kredensial layanan; rantai material ledger masih membutuhkan data MKO. |
| LN-043-T03 | BELUM VALIDASI PENUH | Diberikan hasil fisik berbeda dari forecast yield, ketika receiving dilakukan, maka stok dan nilai memakai fakta aktual, estimasi tidak menimpa qty fisik atau menghasilkan pengurangan ganda. **Catatan:** Pemotongan MD Quality dan beberapa guard berjalan. OCR nyata butuh kredensial layanan; rantai material ledger masih membutuhkan data MKO. |

## L05 — Meja QC dan form inspect tiga sumber

Form interval dan alur QC request/retest mendapat tes runtime. Formula/grade dan pemeriksaan visual seluruh kondisi belum disahkan.

### LN-050 — Permintaan QC dan sumber antrean

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-050-T01 | BELUM VALIDASI PENUH | Diberikan SO tidak minta QC dan SO minta QC seluruh/sampling, ketika diproses, maka hanya kebutuhan yang relevan muncul dan dispatch menunggu QC yang diwajibkan. **Catatan:** Form interval dan alur QC request/retest mendapat tes runtime. Formula/grade dan pemeriksaan visual seluruh kondisi belum disahkan. |
| LN-050-T02 | BELUM VALIDASI PENUH | Diberikan roll retur berbeda dari roll pengganti, ketika inspect pengganti selesai, maka inspection_id, source_type dan daftar roll menunjuk pengganti serta status QC retur tidak berubah keliru. **Catatan:** Form interval dan alur QC request/retest mendapat tes runtime. Formula/grade dan pemeriksaan visual seluruh kondisi belum disahkan. |
| LN-050-T03 | BELUM VALIDASI PENUH | Diberikan random scan roll, ketika form dibuka, maka identitas dan lokasi berasal dari hasil scan sah; roll di luar scope user ditolak. **Catatan:** Form interval dan alur QC request/retest mendapat tes runtime. Formula/grade dan pemeriksaan visual seluruh kondisi belum disahkan. |

### LN-051 — Form inspect sesuai kertas tanpa ambigu satuan

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-051-T01 | BELUM VALIDASI PENUH | Diberikan satu roll basis kg, ketika diinspect 124 yard, maka stok tetap dalam kg dan posisi cacat dalam yard; tidak tampil 124 kg karena salah label. **Catatan:** Form interval dan alur QC request/retest mendapat tes runtime. Formula/grade dan pemeriksaan visual seluruh kondisi belum disahkan. |
| LN-051-T02 | BELUM VALIDASI PENUH | Diberikan roll 165 yard dengan beberapa cacat pada interval yang sama, ketika disimpan/dibuka/print, maka seluruh kejadian dan interval setelah 150 tetap ada, bukan tertimpa/terpotong. **Catatan:** Form interval dan alur QC request/retest mendapat tes runtime. Formula/grade dan pemeriksaan visual seluruh kondisi belum disahkan. |
| LN-051-T03 | BELUM VALIDASI PENUH | Diberikan hasil inspect, ketika ditampilkan pada detail return/SO/export, maka sumber artikel, supplier color, customer dan tanggal pemeriksaan konsisten dengan form. **Catatan:** Form interval dan alur QC request/retest mendapat tes runtime. Formula/grade dan pemeriksaan visual seluruh kondisi belum disahkan. |

### LN-052 — Kamus cacat, perhitungan skor dan grade tervalidasi

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-052-T01 | BELUM VALIDASI PENUH | Diberikan contoh hitung resmi client untuk satu roll, ketika dihitung UI/API/export, maka setiap subtotal, total dan grade identik dengan contoh serta versi formula tersimpan. **Catatan:** Form interval dan alur QC request/retest mendapat tes runtime. Formula/grade dan pemeriksaan visual seluruh kondisi belum disahkan. |
| LN-052-T02 | BELUM VALIDASI PENUH | Diberikan aturan grade berubah tahun berikutnya, ketika laporan lama dibuka, maka hasil historis tidak berubah tanpa proses koreksi yang terlacak. **Catatan:** Form interval dan alur QC request/retest mendapat tes runtime. Formula/grade dan pemeriksaan visual seluruh kondisi belum disahkan. |
| LN-052-T03 | BELUM VALIDASI PENUH | Diberikan KLX-02 belum diputuskan, ketika testing dilakukan, maka hasil formula kandidat diberi status belum tervalidasi dan tidak dianggap bukti kelulusan final. **Catatan:** Form interval dan alur QC request/retest mendapat tes runtime. Formula/grade dan pemeriksaan visual seluruh kondisi belum disahkan. |

## L06 — Sampel, Admin Cutting dan penjualan ecer

Sebagian cutting dan konfigurasi antrean lulus. Catalogue/entitas/lokasi dan dataset knitting belum lengkap untuk seluruh skenario.

### LN-060 — Tiga jenis sampel dan catalogue terurai

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-060-T01 | BELUM VALIDASI PENUH | Diberikan artikel sembilan warna hanya lima tersedia, ketika catalogue dibuat, maka lima komponen 1 yard ditambah satu komponen 2 yard = 7 yard, bukan 11 yard. **Catatan:** Sebagian cutting dan konfigurasi antrean lulus. Catalogue/entitas/lokasi dan dataset knitting belum lengkap untuk seluruh skenario. |
| LN-060-T02 | BELUM VALIDASI PENUH | Diberikan operator mengubah warna soft, ketika disimpan, maka hanya alokasi tambahan 2 yard yang berubah dan masing-masing komponen dasar 1 yard tetap. **Catatan:** Sebagian cutting dan konfigurasi antrean lulus. Catalogue/entitas/lokasi dan dataset knitting belum lengkap untuk seluruh skenario. |
| LN-060-T03 | BELUM VALIDASI PENUH | Diberikan sampel standar 6 yard woven, ketika diajukan, maka tidak melewati batas 5 yard sebagai sampel; penjualan ecer 6 yard memakai jalur berbayar yang sah. **Catatan:** Sebagian cutting dan konfigurasi antrean lulus. Catalogue/entitas/lokasi dan dataset knitting belum lengkap untuk seluruh skenario. |
| LN-060-T04 | BELUM VALIDASI PENUH | Diberikan permintaan hanger woven 0,25 yard, ketika disetujui sesuai kebijakan, maka qty tidak dipaksa naik menjadi 0,5 yard; permintaan 0,6 yard melebihi batas. Untuk knitting, batas 2 kg diperiksa tanpa mengubahnya menjadi panjang tetap. **Catatan:** Sebagian cutting dan konfigurasi antrean lulus. Catalogue/entitas/lokasi dan dataset knitting belum lengkap untuk seluruh skenario. |

### LN-061 — Cutting lintas lokasi/entitas dan Admin Cutting

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-061-T01 | BELUM VALIDASI PENUH | Diberikan sampel Sukacita bersumber roll CST, ketika dipenuhi, maka pembelian/transfer internal dan ownership tercatat sebelum konsumsi/penjualan; stok owner lain tidak terpotong diam-diam. **Catatan:** Sebagian cutting dan konfigurasi antrean lulus. Catalogue/entitas/lokasi dan dataset knitting belum lengkap untuk seluruh skenario. |
| LN-061-T02 | BELUM VALIDASI PENUH | Diberikan catalogue perlu dua lokasi, ketika penugasan dibuat, maka komponen dan transfer memiliki asal/tujuan nyata serta tidak dikirim langsung setelah cutting tanpa handoff Admin Cutting. **Catatan:** Sebagian cutting dan konfigurasi antrean lulus. Catalogue/entitas/lokasi dan dataset knitting belum lengkap untuk seluruh skenario. |
| LN-061-T03 | BELUM VALIDASI PENUH | Diberikan lokasi hanya mengizinkan standar, ketika user memilih catalogue melalui API, maka sistem menerapkan konfigurasi yang sama dengan UI. **Catatan:** Sebagian cutting dan konfigurasi antrean lulus. Catalogue/entitas/lokasi dan dataset knitting belum lengkap untuk seluruh skenario. |

### LN-062 — Ecer berbayar, sisa roll dan mutasi potong

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-062-T01 | BELUM VALIDASI PENUH | Diberikan roll 100 yard dijual ecer 12 yard, ketika selesai dipotong dan dikirim, maka saldo sumber 88 dan penjualan 12 tercatat sekali dengan tagihan yang benar; tidak terkena batas sampel 5 yard. **Catatan:** Sebagian cutting dan konfigurasi antrean lulus. Catalogue/entitas/lokasi dan dataset knitting belum lengkap untuk seluruh skenario. |
| LN-062-T02 | BELUM VALIDASI PENUH | Diberikan proses potong gagal/retry sebelum final, ketika dipulihkan, maka stok tidak terpotong dua kali dan hasil/sisa dapat ditelusuri hingga roll asal. **Catatan:** Sebagian cutting dan konfigurasi antrean lulus. Catalogue/entitas/lokasi dan dataset knitting belum lengkap untuk seluruh skenario. |

## L07 — Picking, transit, multi-SO dispatch dan perjalanan antar lokasi

Sebagian pengujian berjalan; fixture SJ multi-SO bernomor khusus tidak tersedia, sehingga rantai dispatch/transit lengkap belum tervalidasi.

### LN-070 — Picking multi-gudang dan validasi konsolidasi

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-070-T01 | BELUM VALIDASI PENUH | Diberikan tiga SO dengan produk dari gudang woven/knit/printing satu lokasi, ketika dikonsolidasikan, maka picking list dan muatan mencakup tepat roll yang dipilih, tiap SO masih terpisah secara komitmen. **Catatan:** Sebagian pengujian berjalan; fixture SJ multi-SO bernomor khusus tidak tersedia, sehingga rantai dispatch/transit lengkap belum tervalidasi. |
| LN-070-T02 | BELUM VALIDASI PENUH | Diberikan satu roll salah/kurang/berlebih atau alokasi berubah setelah scan, ketika finalisasi dicoba, maka ditolak dengan detail selisih; multi-SO bukan alasan melewati pengecekan. **Catatan:** Sebagian pengujian berjalan; fixture SJ multi-SO bernomor khusus tidak tersedia, sehingga rantai dispatch/transit lengkap belum tervalidasi. |

### LN-071 — Dokumen per leg dan multi-SO manifest

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-071-T01 | BELUM VALIDASI PENUH | Diberikan tiga SO dalam satu trip, ketika dokumen terbit, maka satu manifest memuat semua rincian dan setiap SO memiliki dokumen yang dapat dilacak; nomor ulang/retry tidak menerbitkan pengiriman duplikat. **Catatan:** Sebagian pengujian berjalan; fixture SJ multi-SO bernomor khusus tidak tersedia, sehingga rantai dispatch/transit lengkap belum tervalidasi. |
| LN-071-T02 | BELUM VALIDASI PENUH | Diberikan SO yang belum penuh dan dua keberangkatan, ketika SJ dicetak, maka qty/roll hanya keberangkatan terkait dan aggregate fulfillment tidak melebihi pesanan. **Catatan:** Sebagian pengujian berjalan; fixture SJ multi-SO bernomor khusus tidak tersedia, sehingga rantai dispatch/transit lengkap belum tervalidasi. |

### LN-072 — Transit Jakarta, receipt aktual dan posting yang tepat

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-072-T01 | BELUM VALIDASI PENUH | Diberikan SO dengan dua leg Bandung–Jakarta–customer, ketika sampai Jakarta, maka posisi fisik berubah, komitmen tetap dan customer belum dianggap menerima; GL customer tidak terposting ganda. **Catatan:** Sebagian pengujian berjalan; fixture SJ multi-SO bernomor khusus tidak tersedia, sehingga rantai dispatch/transit lengkap belum tervalidasi. |
| LN-072-T02 | BELUM VALIDASI PENUH | Diberikan Jakarta menerima kurang satu roll, ketika receipt diposting, maka hanya qty aktual berpindah, sisa in-transit/exception terlihat, dan amandemen/susulan memakai keputusan nyata. **Catatan:** Sebagian pengujian berjalan; fixture SJ multi-SO bernomor khusus tidak tersedia, sehingga rantai dispatch/transit lengkap belum tervalidasi. |
| LN-072-T03 | BELUM VALIDASI PENUH | Diberikan restart/retry pada departure, receipt dan customer dispatch, ketika dipulihkan, maka stok, dokumen dan jurnal tetap tepat satu kali per peristiwa. **Catatan:** Sebagian pengujian berjalan; fixture SJ multi-SO bernomor khusus tidak tersedia, sehingga rantai dispatch/transit lengkap belum tervalidasi. |

## L08 — Menu Retur terpadu, penerimaan, QC dan lineage roll

Sumber roll retur dan perjalanan QC membutuhkan SO terkirim serta gudang Rancamalang pada dataset KN. Tidak dapat dinyatakan selesai dari tes batch ini.

### LN-080 — Form retur dan menu yang jelas

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-080-T01 | BELUM VALIDASI PENUH | Diberikan SO hanya sebagian dikirim, ketika form retur dibuka, maka hanya roll/qty terkirim yang dapat dipilih; product ID mentah tidak tampil sebagai nama dan qty/unit terisi benar. **Catatan:** Sumber roll retur dan perjalanan QC membutuhkan SO terkirim serta gudang Rancamalang pada dataset KN. Tidak dapat dinyatakan selesai dari tes batch ini. |
| LN-080-T02 | BELUM VALIDASI PENUH | Diberikan satu roll pernah diretur sebagian, ketika klaim kedua dibuat paralel, maka batas kumulatif qty retur dijaga atomik dan barang belum terkirim/tidak terkait tidak dapat ditambahkan. **Catatan:** Sumber roll retur dan perjalanan QC membutuhkan SO terkirim serta gudang Rancamalang pada dataset KN. Tidak dapat dinyatakan selesai dari tes batch ini. |
| LN-080-T03 | BELUM VALIDASI PENUH | Diberikan bukti belum lengkap, ketika kebijakan mengizinkan draft/proses, maka dapat dilengkapi kemudian; jika wajib pada tahap tertentu, validasi UI/API sesuai konfigurasi. **Catatan:** Sumber roll retur dan perjalanan QC membutuhkan SO terkirim serta gudang Rancamalang pada dataset KN. Tidak dapat dinyatakan selesai dari tes batch ini. |
| LN-080-T04 | BELUM VALIDASI PENUH | Diberikan user memfilter status dan kategori, ketika list/kartu total/detail dibuka, maka definisi hitungan jelas dan tidak memberi total yang berbeda tanpa label scope. **Catatan:** Sumber roll retur dan perjalanan QC membutuhkan SO terkirim serta gudang Rancamalang pada dataset KN. Tidak dapat dinyatakan selesai dari tes batch ini. |

### LN-081 — Pisahkan perjalanan fisik, QC, keputusan dan saldo

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-081-T01 | BELUM VALIDASI PENUH | Diberikan retur diterima Jakarta lalu dikirim Rancamalang, ketika setiap tahap discan, maka roll terlihat Jakarta → in transit → area QC Rancamalang dengan dokumen aktual, bukan langsung pindah lokasi karena klik keputusan. **Catatan:** Sumber roll retur dan perjalanan QC membutuhkan SO terkirim serta gudang Rancamalang pada dataset KN. Tidak dapat dinyatakan selesai dari tes batch ini. |
| LN-081-T02 | BELUM VALIDASI PENUH | Diberikan return disetujui tetapi belum QC, ketika settlement/tukar final dicoba, maka tidak memicu refund/stock available final; permission dan bukti keputusan tetap terekam. **Catatan:** Sumber roll retur dan perjalanan QC membutuhkan SO terkirim serta gudang Rancamalang pada dataset KN. Tidak dapat dinyatakan selesai dari tes batch ini. |
| LN-081-T03 | BELUM VALIDASI PENUH | Diberikan satu kasus berisi yard dan kg, ketika ringkasan chain dihitung, maka total dipisah per satuan dan uang menggunakan basis nilai, bukan menjumlah 100 yard + 20 kg sebagai 120 yard. **Catatan:** Sumber roll retur dan perjalanan QC membutuhkan SO terkirim serta gudang Rancamalang pada dataset KN. Tidak dapat dinyatakan selesai dari tes batch ini. |

### LN-082 — Identitas unik, potongan dan larangan kembali ke customer asal

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-082-T01 | BELUM VALIDASI PENUH | Diberikan roll utuh kembali dengan qty/grade berubah, ketika diterima dan QC selesai, maka identitas tetap dapat ditelusuri ke pengiriman asli dan qty bruto/aktual/grade lama-baru tersimpan. **Catatan:** Sumber roll retur dan perjalanan QC membutuhkan SO terkirim serta gudang Rancamalang pada dataset KN. Tidak dapat dinyatakan selesai dari tes batch ini. |
| LN-082-T02 | BELUM VALIDASI PENUH | Diberikan dua operator membuat potongan dari induk sama bersamaan, ketika commit, maka ID child berbeda, jumlah panjang/berat hasil+sisa+waste sama dengan input dalam basis masing-masing. **Catatan:** Sumber roll retur dan perjalanan QC membutuhkan SO terkirim serta gudang Rancamalang pada dataset KN. Tidak dapat dinyatakan selesai dari tes batch ini. |
| LN-082-T03 | BELUM VALIDASI PENUH | Diberikan potongan retur milik customer A, ketika akan dialokasi ke A lagi, maka diblok selama kebijakan aktif walau child sudah ganti owner; user tanpa hak tidak bisa mematikan toggle. **Catatan:** Sumber roll retur dan perjalanan QC membutuhkan SO terkirim serta gudang Rancamalang pada dataset KN. Tidak dapat dinyatakan selesai dari tes batch ini. |

### LN-083 — Batas waktu, eligibility dan bukti keputusan

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-083-T01 | BELUM VALIDASI PENUH | Diberikan customer masih dalam batas dan supplier sudah lewat batas, ketika klaim dicatat, maka customer tidak otomatis ditolak hanya karena supplier kedaluwarsa. **Catatan:** Sumber roll retur dan perjalanan QC membutuhkan SO terkirim serta gudang Rancamalang pada dataset KN. Tidak dapat dinyatakan selesai dari tes batch ini. |
| LN-083-T02 | BELUM VALIDASI PENUH | Diberikan dua receiving dengan tanggal berbeda pada satu PO, ketika kebijakan supplier ditampilkan, maka deadline mengacu receiving roll masing-masing, bukan tanggal PO terakhir. **Catatan:** Sumber roll retur dan perjalanan QC membutuhkan SO terkirim serta gudang Rancamalang pada dataset KN. Tidak dapat dinyatakan selesai dari tes batch ini. |
| LN-083-T03 | BELUM VALIDASI PENUH | Diberikan KLR-08/KLR-09 belum jelas, ketika pengujian eligibility final dilakukan, maka bagian tersebut tetap pending dan tidak mengubah semua kasus menjadi diterima/ditolak secara asumsi. **Catatan:** Sumber roll retur dan perjalanan QC membutuhkan SO terkirim serta gudang Rancamalang pada dataset KN. Tidak dapat dinyatakan selesai dari tes batch ini. |

## L09 — Tukar, kompensasi, retur interco dan supplier end-to-end

Sebagian tes guard berjalan; provenance PO, tukar barang, supplier dan penyelesaian Finance belum diuji sebagai satu rantai lengkap.

### LN-090 — Tukar barang sampai customer

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-090-T01 | BELUM VALIDASI PENUH | Diberikan retur belum QC, ketika Admin Sales mencoba final dispatch pengganti, maka diblok tanpa membuat stock out/jurnal. **Catatan:** Sebagian tes guard berjalan; provenance PO, tukar barang, supplier dan penyelesaian Finance belum diuji sebagai satu rantai lengkap. |
| LN-090-T02 | BELUM VALIDASI PENUH | Diberikan kasus QC selesai dan SO awal meminta QC, ketika pengganti dipilih, maka warna/grade/artikel sama, QC pengganti diwajibkan, dan SJ/POD terhubung hingga kasus; bila SO awal tanpa QC maka tidak diwajibkan karena flag itu. **Catatan:** Sebagian tes guard berjalan; provenance PO, tukar barang, supplier dan penyelesaian Finance belum diuji sebagai satu rantai lengkap. |
| LN-090-T03 | BELUM VALIDASI PENUH | Diberikan pengganti berbeda qty, ketika alur dijalankan, maka hasil akhir menggunakan keputusan KLR-03/04/05 yang disetujui; sebelum jawaban, tidak ada tagihan/penghapusan selisih otomatis. **Catatan:** Sebagian tes guard berjalan; provenance PO, tukar barang, supplier dan penyelesaian Finance belum diuji sebagai satu rantai lengkap. |

### LN-091 — Refund/saldo, potong tagihan dan nilai histori

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-091-T01 | BELUM VALIDASI PENUH | Diberikan credit disetujui 30, tagihan sumber 20 dan customer pilih saldo, ketika diposting, maka tagihan berkurang 20 dan saldo 10; jika pilih refund maka pembayaran keluar 10, bukan 30 ditambah saldo lagi. **Catatan:** Sebagian tes guard berjalan; provenance PO, tukar barang, supplier dan penyelesaian Finance belum diuji sebagai satu rantai lengkap. |
| LN-091-T02 | BELUM VALIDASI PENUH | Diberikan barang retur turun grade, ketika jurnal/stock valuation dibuat, maka rekonsiliasi stok, nilai persediaan, credit customer, AR dan impairment terpisah serta seimbang, tidak mengubah invoice historis. **Catatan:** Sebagian tes guard berjalan; provenance PO, tukar barang, supplier dan penyelesaian Finance belum diuji sebagai satu rantai lengkap. |
| LN-091-T03 | BELUM VALIDASI PENUH | Diberikan retry settlement bersamaan, ketika diproses, maka nota kredit, saldo, refund dan restock masing-masing tidak dobel; recovery mempunyai status yang jelas. **Catatan:** Sebagian tes guard berjalan; provenance PO, tukar barang, supplier dan penyelesaian Finance belum diuji sebagai satu rantai lengkap. |

### LN-092 — Cutloss dan discount hanya setelah kebijakan final

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-092-T01 | BELUM VALIDASI PENUH | Diberikan keputusan cutloss resmi, ketika contoh 120 yard diuji, maka qty customer, stock tersisa, potongan, waste dan nilai refund sama dengan keputusan; semua qty dapat direkonsiliasi. **Catatan:** Sebagian tes guard berjalan; provenance PO, tukar barang, supplier dan penyelesaian Finance belum diuji sebagai satu rantai lengkap. |
| LN-092-T02 | BELUM VALIDASI PENUH | Diberikan discount tanpa barang kembali, ketika disetujui, maka evidence/QC exception dan basis nominal sesuai kebijakan final; stok gudang tidak bertambah seolah barang diterima. **Catatan:** Sebagian tes guard berjalan; provenance PO, tukar barang, supplier dan penyelesaian Finance belum diuji sebagai satu rantai lengkap. |
| LN-092-T03 | BELUM VALIDASI PENUH | Diberikan keputusan belum ada, ketika agent menyiapkan rilis, maka cabang dependent tidak diklaim selesai atau dibuka dengan default yang dipilih sendiri. **Catatan:** Sebagian tes guard berjalan; provenance PO, tukar barang, supplier dan penyelesaian Finance belum diuji sebagai satu rantai lengkap. |

### LN-093 — Sukacita → CST → supplier dengan provenance benar

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-093-T01 | BELUM VALIDASI PENUH | Diberikan barang Sukacita bersumber CST, ketika dipilih simpan, maka owner tetap Sukacita; ketika dipilih retur internal, maka owner CST, dokumen/jurnal interco berpasangan dan posisi fisik shared yang sama tidak berubah fiktif. **Catatan:** Sebagian tes guard berjalan; provenance PO, tukar barang, supplier dan penyelesaian Finance belum diuji sebagai satu rantai lengkap. |
| LN-093-T02 | BELUM VALIDASI PENUH | Diberikan kasus berisi roll dari dua PO/supplier, ketika retur supplier dibuat, maka dipisah menurut provenance asli dan semua dokumen terhubung ke SO/kasus; tidak memilih PO terbaru berdasarkan nama produk saja. **Catatan:** Sebagian tes guard berjalan; provenance PO, tukar barang, supplier dan penyelesaian Finance belum diuji sebagai satu rantai lengkap. |
| LN-093-T03 | BELUM VALIDASI PENUH | Diberikan CST supplier window lewat, ketika diputuskan simpan, maka tidak otomatis berstatus siap jual jika QC/grade/hold melarang; disposal BS mengurangi fisik dengan bukti dan jurnal yang sesuai. **Catatan:** Sebagian tes guard berjalan; provenance PO, tukar barang, supplier dan penyelesaian Finance belum diuji sebagai satu rantai lengkap. |
| LN-093-T04 | BELUM VALIDASI PENUH | Diberikan retry internal return atau receipt, ketika dijalankan kembali, maka stock owner, AP/AR interco dan referensi supplier tidak berlipat. **Catatan:** Sebagian tes guard berjalan; provenance PO, tukar barang, supplier dan penyelesaian Finance belum diuji sebagai satu rantai lengkap. |

## L10 — Putaway, stock opname, dashboard dan Meja User

27 kasus WMS/opname unik lulus setelah fixture lokasi dilengkapi. Recovery gangguan jurnal AUD-WMS-01 tetap gagal. UI menyeluruh dan perangkat belum diuji.

### LN-100 — Alamat fisik dan putaway yang dapat dipakai

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-100-T01 | BELUM VALIDASI PENUH | Diberikan satu lokasi tiga gudang dan satu lemari beberapa rak, ketika stok ditempatkan, maka alamat lengkap terlihat dan qty per tingkat menuruni struktur yang benar. **Catatan:** 27 kasus WMS/opname unik lulus setelah fixture lokasi dilengkapi. Recovery gangguan jurnal AUD-WMS-01 tetap gagal. UI menyeluruh dan perangkat belum diuji. |
| LN-100-T02 | BELUM VALIDASI PENUH | Diberikan shared gudang dengan woven-only node, ketika roll CST/Sukacita cocok kategori masuk, maka diterima tanpa gudang owner fiktif; roll knit ditolak dengan alasan jelas. **Catatan:** 27 kasus WMS/opname unik lulus setelah fixture lokasi dilengkapi. Recovery gangguan jurnal AUD-WMS-01 tetap gagal. UI menyeluruh dan perangkat belum diuji. |
| LN-100-T03 | BELUM VALIDASI PENUH | Diberikan rak berstok atau tugas aktif, ketika dipindah/dinonaktifkan, maka referensi dilindungi atau migrasi eksplisit menjaga alamat, kapasitas dan tugas. **Catatan:** 27 kasus WMS/opname unik lulus setelah fixture lokasi dilengkapi. Recovery gangguan jurnal AUD-WMS-01 tetap gagal. UI menyeluruh dan perangkat belum diuji. |

### LN-101 — Stock opname fisik, identitas, qty dan rekonsiliasi

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-101-T01 | TERUJI API LOKAL | Diberikan scan satu roll dua kali, satu hilang dan satu salah rak, ketika hasil dibandingkan snapshot, maka tiga situasi dibedakan dan duplikasi scan tidak menambah stok. **Catatan:** Teruji pada fixture lokal: duplikat scan, roll hilang, salah alamat dibedakan. Bukti wms-extra-run.xml. Bukan sign-off seluruh opname. |
| LN-101-T02 | BELUM VALIDASI PENUH | Diberikan movement setelah snapshot selama hitung, ketika selisih difinalisasi, maka mekanisme cutoff/delta menghasilkan saldo benar dan adjustment tidak mengulang gerakan yang sudah diposting. **Catatan:** 27 kasus WMS/opname unik lulus setelah fixture lokasi dilengkapi. Recovery gangguan jurnal AUD-WMS-01 tetap gagal. UI menyeluruh dan perangkat belum diuji. |
| LN-101-T03 | TEMUAN TERBUKTI | Diberikan counter tanpa hak ACC, ketika mencoba adjustment langsung lewat API, maka ditolak; retry adjustment sah mengubah saldo/jurnal sekali. **Catatan:** AUD-WMS-01: retry setelah kegagalan GL tidak memulihkan jurnal. |

### LN-102 — Dashboard stok dan antrean Meja User yang konsisten

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-102-T01 | TERUJI API LOKAL | Diberikan stok 100 yard owner A dan 20 kg owner B pada node berbeda, ketika drill-down dan filter dijalankan, maka total dipisah unit dan agregasi parent = child sesuai scope; roll di QC hold tidak available. **Catatan:** Teruji API: 100 yard owner A, 20 kg owner B, QC hold 50 yard, agregasi parent/child dan filter owner. Bukti wms-run/test_l10_ln100_ln102_stock_tree.xml. UI drill-down belum ditelusuri lengkap. |
| LN-102-T02 | BELUM VALIDASI PENUH | Diberikan kartu antrean pending 4, ketika diklik, maka empat dokumen yang sama muncul dan setiap item membuka halaman terkait dengan izin yang benar. **Catatan:** 27 kasus WMS/opname unik lulus setelah fixture lokasi dilengkapi. Recovery gangguan jurnal AUD-WMS-01 tetap gagal. UI menyeluruh dan perangkat belum diuji. |
| LN-102-T03 | BELUM VALIDASI PENUH | Diberikan perpindahan lokasi tanpa ganti owner, ketika dashboard stok dan Finance dibandingkan, maka tidak ada penjualan/pembelian atau doubling saldo karena movement internal. **Catatan:** 27 kasus WMS/opname unik lulus setelah fixture lokasi dilengkapi. Recovery gangguan jurnal AUD-WMS-01 tetap gagal. UI menyeluruh dan perangkat belum diuji. |

## L11 — Pusat export, join bisnis dan rapor staf

Partisi XLSX lebih dari 5.000 baris sudah lulus. Grouping download dan konsistensi sumber berubah tetap bermasalah; mapping seluruh collection belum tuntas.

### LN-110 — Registry seluruh data bisnis dan builder export

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-110-T01 | TEMUAN TERBUKTI | Diberikan user memilih tanggal, kolom dan filter A AND (B OR C), ketika preview dan export dibuat pada snapshot/filter sama, maka data, tipe, urutan dan total cocok. **Catatan:** AUD-EXP-02: perubahan sumber antarbatch menggandakan ID, count tetap cocok. |
| LN-110-T02 | BELUM VALIDASI PENUH | Diberikan collection bisnis baru, ketika inventory dibanding registry, maka ada mapping dataset atau alasan akses/pengecualian terdokumentasi, bukan diam-diam tidak ikut cakupan. **Catatan:** Partisi XLSX lebih dari 5.000 baris sudah lulus. Grouping download dan konsistensi sumber berubah tetap bermasalah; mapping seluruh collection belum tuntas. |
| LN-110-T03 | TERUJI API LOKAL | Diberikan data melebihi page size/batas Excel sheet, ketika export dilakukan, maka tidak terpotong diam-diam; format/partisi dan jumlah total dijelaskan di hasil. **Catatan:** Teruji pembagian sheet 5.000 dengan tambahan 5.001 movement sintetis; seluruh baris cocok. Bukti export-volume.xml. Belum stress test batas Excel satu juta baris. |

### LN-111 — Join relevan, grain dan Finance analytics

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-111-T01 | BELUM VALIDASI PENUH | Diberikan dua item SO, dua pembayaran dan dua shipment, ketika laporan per item atau customer diexport, maka nilai penjualan tidak menjadi empat kali dan pembayaran tidak terduplikasi. **Catatan:** Partisi XLSX lebih dari 5.000 baris sudah lulus. Grouping download dan konsistensi sumber berubah tetap bermasalah; mapping seluruh collection belum tuntas. |
| LN-111-T02 | BELUM VALIDASI PENUH | Diberikan user memilih sales A/B/C untuk artikel A atau customer A oleh sales A, ketika filter/join dipakai, maka hasil dan total cocok dengan transaksi sumber serta tidak mengubah attribution karena assignment customer saat ini berganti. **Catatan:** Partisi XLSX lebih dari 5.000 baris sudah lulus. Grouping download dan konsistensi sumber berubah tetap bermasalah; mapping seluruh collection belum tuntas. |
| LN-111-T03 | BELUM VALIDASI PENUH | Diberikan order dan payment berbeda bulan, ketika basis tanggal berubah, maka laporan berubah sesuai definisi yang ditampilkan, bukan mencampur order date dan payment date tanpa penjelasan. **Catatan:** Partisi XLSX lebih dari 5.000 baris sudah lulus. Grouping download dan konsistensi sumber berubah tetap bermasalah; mapping seluruh collection belum tuntas. |

### LN-112 — Rapor Designer dan Sales lengkap

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-112-T01 | BELUM VALIDASI PENUH | Diberikan Designer A membuat 15 versi, sebagian belum dinilai, ketika rapor periode dibuat, maka semua versi relevan tampil, nilai kosong tidak menurunkan rata-rata sebagai nol, jumlah revisi dan ringkasan sama dengan sumber. **Catatan:** Partisi XLSX lebih dari 5.000 baris sudah lulus. Grouping download dan konsistensi sumber berubah tetap bermasalah; mapping seluruh collection belum tuntas. |
| LN-112-T02 | BELUM VALIDASI PENUH | Diberikan desain dibuat staf A lalu dialihkan B, ketika rapor dibuat, maka pembuat/assignment/penilai dibedakan dan tidak menisbatkan semua kerja ke nama terakhir. **Catatan:** Partisi XLSX lebih dari 5.000 baris sudah lulus. Grouping download dan konsistensi sumber berubah tetap bermasalah; mapping seluruh collection belum tuntas. |
| LN-112-T03 | BELUM VALIDASI PENUH | Diberikan SO sales team split dan kemudian retur, ketika rapor Sales dihitung, maka attribution tidak memberikan 100 persen nilai yang sama kepada semua orang dan net sales tidak disamakan dengan kas diterima. **Catatan:** Partisi XLSX lebih dari 5.000 baris sudah lulus. Grouping download dan konsistensi sumber berubah tetap bermasalah; mapping seluruh collection belum tuntas. |

### LN-113 — Keamanan field dan konsistensi pekerjaan export

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-113-T01 | BELUM VALIDASI PENUH | Diberikan Sales tidak berhak grade/owner, ketika kolom disisipkan manual ke API export atau join, maka ditolak/disembunyikan sesuai registry tanpa bocor lewat preview/summary. **Catatan:** Partisi XLSX lebih dari 5.000 baris sudah lulus. Grouping download dan konsistensi sumber berubah tetap bermasalah; mapping seluruh collection belum tuntas. |
| LN-113-T02 | BELUM VALIDASI PENUH | Diberikan akses user dicabut setelah job selesai, ketika unduh dicoba, maka hak diperiksa lagi dan file tidak dapat diakses user lain tanpa izin. **Catatan:** Partisi XLSX lebih dari 5.000 baris sudah lulus. Grouping download dan konsistensi sumber berubah tetap bermasalah; mapping seluruh collection belum tuntas. |
| LN-113-T03 | BELUM VALIDASI PENUH | Diberikan nilai nama customer diawali karakter formula spreadsheet, ketika file dibuka, maka diperlakukan sebagai teks, bukan formula aktif. **Catatan:** Partisi XLSX lebih dari 5.000 baris sudah lulus. Grouping download dan konsistensi sumber berubah tetap bermasalah; mapping seluruh collection belum tuntas. |

## L12 — Kesiapan ERP untuk middleware Chainway dan UAT tiga perangkat

Tes identitas device berjalan. Main bersih belum dibuktikan memiliki seluruh kontrak middleware 0.5; UAT perangkat belum dilakukan.

### LN-120 — Parity kontrak dan pemisahan modul

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-120-T01 | BELUM VALIDASI PENUH | Diberikan OpenAPI manual dan ERP aktual, ketika parity matrix dibuat, maka setiap operation/error/ACK dan ERP-MW gap punya implementasi atau backlog jelas serta source SHA; tidak menganggap kontrak ada hanya karena tertulis di manual. **Catatan:** Tes identitas device berjalan. Main bersih belum dibuktikan memiliki seluruh kontrak middleware 0.5; UAT perangkat belum dilakukan. |
| LN-120-T02 | BELUM VALIDASI PENUH | Diberikan tiga device identity, ketika permission/scope diuji, maka masing-masing hanya dapat mengakses tugas dan lokasi yang diizinkan, tanpa token user bersama hardcoded. **Catatan:** Tes identitas device berjalan. Main bersih belum dibuktikan memiliki seluruh kontrak middleware 0.5; UAT perangkat belum dilakukan. |
| MW-INT-01 | MENUNGGU UAT PERANGKAT | Jalankan skenario INT-01 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-INT-02 | MENUNGGU UAT PERANGKAT | Jalankan skenario INT-02 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-INT-03 | MENUNGGU UAT PERANGKAT | Jalankan skenario INT-03 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-INT-04 | MENUNGGU UAT PERANGKAT | Jalankan skenario INT-04 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-INT-05 | MENUNGGU UAT PERANGKAT | Jalankan skenario INT-05 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-INT-06 | MENUNGGU UAT PERANGKAT | Jalankan skenario INT-06 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-INT-07 | MENUNGGU UAT PERANGKAT | Jalankan skenario INT-07 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-INT-08 | MENUNGGU UAT PERANGKAT | Jalankan skenario INT-08 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-INT-09 | MENUNGGU UAT PERANGKAT | Jalankan skenario INT-09 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-INT-10 | MENUNGGU UAT PERANGKAT | Jalankan skenario INT-10 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-INT-11 | MENUNGGU UAT PERANGKAT | Jalankan skenario INT-11 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-INT-12 | MENUNGGU UAT PERANGKAT | Jalankan skenario INT-12 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |

### LN-121 — UR300/C72: durability, context dan keputusan bisnis

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-121-T01 | BELUM VALIDASI PENUH | Diberikan batch offline dikirim ulang setelah restart, ketika ERP ACK dan process, maka tidak hilang event dan tidak double posting; keputusan gate tidak dijalankan berdasarkan bacaan lama. **Catatan:** Tes identitas device berjalan. Main bersih belum dibuktikan memiliki seluruh kontrak middleware 0.5; UAT perangkat belum dilakukan. |
| LN-121-T02 | BELUM VALIDASI PENUH | Diberikan C72 task di luar lokasi atau bin tak sesuai aturan, ketika scan submit, maka ditolak dengan sebab yang jelas tanpa merubah saldo. **Catatan:** Tes identitas device berjalan. Main bersih belum dibuktikan memiliki seluruh kontrak middleware 0.5; UAT perangkat belum dilakukan. |
| LN-121-T03 | MENUNGGU UAT PERANGKAT | Diberikan UR300 native Android pada lokasi pilot, ketika listrik/jaringan pulih, maka proses harian berjalan tanpa laptop serta event dan keputusan dapat direkonsiliasi end-to-end. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-HH-01 | MENUNGGU UAT PERANGKAT | Jalankan skenario HH-01 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-HH-02 | MENUNGGU UAT PERANGKAT | Jalankan skenario HH-02 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-HH-03 | MENUNGGU UAT PERANGKAT | Jalankan skenario HH-03 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-HH-04 | MENUNGGU UAT PERANGKAT | Jalankan skenario HH-04 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-HH-05 | MENUNGGU UAT PERANGKAT | Jalankan skenario HH-05 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-HH-06 | MENUNGGU UAT PERANGKAT | Jalankan skenario HH-06 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-HH-07 | MENUNGGU UAT PERANGKAT | Jalankan skenario HH-07 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-HH-08 | MENUNGGU UAT PERANGKAT | Jalankan skenario HH-08 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-HH-09 | MENUNGGU UAT PERANGKAT | Jalankan skenario HH-09 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-HH-10 | MENUNGGU UAT PERANGKAT | Jalankan skenario HH-10 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-HH-11 | MENUNGGU UAT PERANGKAT | Jalankan skenario HH-11 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-HH-12 | MENUNGGU UAT PERANGKAT | Jalankan skenario HH-12 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-RD-01 | MENUNGGU UAT PERANGKAT | Jalankan skenario RD-01 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-RD-02 | MENUNGGU UAT PERANGKAT | Jalankan skenario RD-02 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-RD-03 | MENUNGGU UAT PERANGKAT | Jalankan skenario RD-03 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-RD-04 | MENUNGGU UAT PERANGKAT | Jalankan skenario RD-04 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-RD-05 | MENUNGGU UAT PERANGKAT | Jalankan skenario RD-05 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-RD-06 | MENUNGGU UAT PERANGKAT | Jalankan skenario RD-06 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-RD-07 | MENUNGGU UAT PERANGKAT | Jalankan skenario RD-07 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-RD-08 | MENUNGGU UAT PERANGKAT | Jalankan skenario RD-08 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-RD-09 | MENUNGGU UAT PERANGKAT | Jalankan skenario RD-09 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-RD-10 | MENUNGGU UAT PERANGKAT | Jalankan skenario RD-10 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-RD-11 | MENUNGGU UAT PERANGKAT | Jalankan skenario RD-11 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-RD-12 | MENUNGGU UAT PERANGKAT | Jalankan skenario RD-12 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |

### LN-122 — CP30EN print/encode/verify dan reprint yang aman

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-122-T01 | BELUM VALIDASI PENUH | Diberikan printer mencetak tetapi ACK hilang, ketika koneksi pulih, maka job masuk reconcile/unknown dan tidak otomatis mencetak/encode tag baru. **Catatan:** Tes identitas device berjalan. Main bersih belum dibuktikan memiliki seluruh kontrak middleware 0.5; UAT perangkat belum dilakukan. |
| LN-122-T02 | BELUM VALIDASI PENUH | Diberikan batch sepuluh tag dengan tiga hasil unknown, ketika retry, maka hanya hasil yang aman ditindaklanjuti, identitas fisik dan status job dapat dicocokkan. **Catatan:** Tes identitas device berjalan. Main bersih belum dibuktikan memiliki seluruh kontrak middleware 0.5; UAT perangkat belum dilakukan. |
| LN-122-T03 | MENUNGGU UAT PERANGKAT | Diberikan CP30EN dan label aktual, ketika print–encode–read C72–read UR300 dilakukan, maka EPC, teks, identitas roll dan saldo ERP sama serta bukti perangkat/firmware/media disimpan. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-PR-01 | MENUNGGU UAT PERANGKAT | Jalankan skenario PR-01 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-PR-02 | MENUNGGU UAT PERANGKAT | Jalankan skenario PR-02 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-PR-03 | MENUNGGU UAT PERANGKAT | Jalankan skenario PR-03 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-PR-04 | MENUNGGU UAT PERANGKAT | Jalankan skenario PR-04 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-PR-05 | MENUNGGU UAT PERANGKAT | Jalankan skenario PR-05 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-PR-06 | MENUNGGU UAT PERANGKAT | Jalankan skenario PR-06 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-PR-07 | MENUNGGU UAT PERANGKAT | Jalankan skenario PR-07 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-PR-08 | MENUNGGU UAT PERANGKAT | Jalankan skenario PR-08 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-PR-09 | MENUNGGU UAT PERANGKAT | Jalankan skenario PR-09 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-PR-10 | MENUNGGU UAT PERANGKAT | Jalankan skenario PR-10 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-PR-11 | MENUNGGU UAT PERANGKAT | Jalankan skenario PR-11 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| MW-PR-12 | MENUNGGU UAT PERANGKAT | Jalankan skenario PR-12 pada integrasi ERP–middleware sesuai sources/middleware/uat/UAT_SCENARIOS.md, simpan input, expected dan actual per langkah. Batas lingkup: validasi integrasi, bukan perintah membangun ulang middleware. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |

## L13 — Absensi langsung perangkat ke ERP

Belum ada bukti pengujian perangkat absensi nyata maupun seluruh aturan HR turunan.

### LN-130 — Kontrak direct attendance dan raw log

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-130-T01 | MENUNGGU UAT PERANGKAT | Diberikan device asli dan employee ID mapping, ketika punch langsung ERP tanpa laptop, maka raw log tersimpan sekali dengan waktu asal dan waktu diterima; karyawan salah mapping masuk exception. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| LN-130-T02 | MENUNGGU UAT PERANGKAT | Diberikan jaringan terputus lalu batch replay, ketika pulih, maka seluruh punch kembali tanpa dobel dan tidak disamakan dengan waktu received saja. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |
| LN-130-T03 | MENUNGGU UAT PERANGKAT | Diberikan firmware berbeda dari yang diuji, ketika commissioning, maka kemampuan protokol diverifikasi ulang dan tidak memakai bukti model lain sebagai kelulusan. **Catatan:** Belum ada bukti perangkat fisik untuk acceptance ini. |

### LN-131 — Attendance turunan, koreksi dan aturan HR

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-131-T01 | BELUM VALIDASI PENUH | Diberikan shift melewati tengah malam dan punch berulang, ketika aturan HR resmi diterapkan, maka attendance dan tanggal kerja sesuai contoh yang disetujui, bukan asal kalender hari punch. **Catatan:** Belum ada bukti pengujian perangkat absensi nyata maupun seluruh aturan HR turunan. |
| LN-131-T02 | BELUM VALIDASI PENUH | Diberikan HR mengoreksi hasil turunan lalu recompute, ketika diproses, maka override sah tetap terlacak dan raw log tidak berubah. **Catatan:** Belum ada bukti pengujian perangkat absensi nyata maupun seluruh aturan HR turunan. |
| LN-131-T03 | BELUM VALIDASI PENUH | Diberikan aturan HR belum ada, ketika paket diuji, maka raw ingestion boleh dibuktikan terpisah tetapi attendance/payroll tidak diklaim tervalidasi. **Catatan:** Belum ada bukti pengujian perangkat absensi nyata maupun seluruh aturan HR turunan. |

## L14 — Integrasi, migrasi, UAT dan penutupan gelombang

Belum closure: validator metadata melaporkan 317 hambatan. Ini bukan 317 bug aplikasi; migrasi, UAT dan chain end-to-end belum tuntas.

### LN-140 — Rantai bisnis dan Finance pada satu kandidat rilis

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-140-T01 | BELUM VALIDASI PENUH | Diberikan fixture L00, ketika semua rantai dijalankan pada kandidat, maka qty per unit, identitas, owner, alamat, reservation, dokumen, saldo customer, AR/AP, inventory valuation dan GL sesuai checkpoint dan tidak double posting. **Catatan:** Belum closure: validator metadata melaporkan 317 hambatan. Ini bukan 317 bug aplikasi; migrasi, UAT dan chain end-to-end belum tuntas. |
| LN-140-T02 | BELUM VALIDASI PENUH | Diberikan kegagalan setelah cetak/issue/QC/settlement tetapi sebelum ACK, ketika dipulihkan, maka operasi dapat direkonsiliasi tanpa transaksi hilang atau berlipat. **Catatan:** Belum closure: validator metadata melaporkan 317 hambatan. Ini bukan 317 bug aplikasi; migrasi, UAT dan chain end-to-end belum tuntas. |

### LN-141 — Migrasi dan batas cakupan yang terukur

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-141-T01 | BELUM VALIDASI PENUH | Diberikan data lama tanpa roll link/provenance, ketika migrasi dry-run, maka ditandai membutuhkan rekonsiliasi, bukan dipasangkan ke PO produk terakhir secara otomatis. **Catatan:** Belum closure: validator metadata melaporkan 317 hambatan. Ini bukan 317 bug aplikasi; migrasi, UAT dan chain end-to-end belum tuntas. |
| LN-141-T02 | BELUM VALIDASI PENUH | Diberikan schema baru di-rollback/dipulihkan dari backup uji, ketika dibandingkan, maka saldo dan hubungan dokumen dapat direkonsiliasi; penomoran dan posting tidak berulang. **Catatan:** Belum closure: validator metadata melaporkan 317 hambatan. Ini bukan 317 bug aplikasi; migrasi, UAT dan chain end-to-end belum tuntas. |
| LN-141-T03 | BELUM VALIDASI PENUH | Diberikan requirement dan acceptance pending, ketika laporan cakupan dibuat, maka pending/fail/not_run dilaporkan eksplisit dan tidak masuk persentase PASS. **Catatan:** Belum closure: validator metadata melaporkan 317 hambatan. Ini bukan 317 bug aplikasi; migrasi, UAT dan chain end-to-end belum tuntas. |

### LN-142 — UAT dan definisi selesai

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-142-T01 | BELUM VALIDASI PENUH | Diberikan requirement blocked atau acceptance not_run, ketika agent meminta complete, maka validator menolak meskipun build dan unit test lulus. **Catatan:** Belum closure: validator metadata melaporkan 317 hambatan. Ini bukan 317 bug aplikasi; migrasi, UAT dan chain end-to-end belum tuntas. |
| LN-142-T02 | BELUM VALIDASI PENUH | Diberikan semua bukti final beserta persetujuan owner dan reviewer yang berbeda dari implementer, ketika closure dijalankan, maka SHA, tanggal, jumlah requirement/acceptance dan sisa risiko tercantum serta dapat dilacak. **Catatan:** Belum closure: validator metadata melaporkan 317 hambatan. Ini bukan 317 bug aplikasi; migrasi, UAT dan chain end-to-end belum tuntas. |

### LN-143 — Validasi produksi Pesanan Khusus hingga penerimaan, Finance dan pengiriman

| Acceptance | Status audit | Skenario dan catatan |
|---|---|---|
| LN-143-T01 | BELUM VALIDASI PENUH | E2E supplier: ACC uji relevan -> PR/PO -> receipt parsial/final -> status kualitas yang berlaku -> stok eligible -> alokasi SO -> picking/dispatch/SJ -> customer. Qty tersisa dan status per item benar; baru PO dibuat bukan bukti produksi fisik atau barang siap kirim. **Catatan:** Belum closure: validator metadata melaporkan 317 hambatan. Ini bukan 317 bug aplikasi; migrasi, UAT dan chain end-to-end belum tuntas. |
| LN-143-T02 | BELUM VALIDASI PENUH | E2E makloon: ACC -> PR/MKO -> reserve bahan -> issue -> receipt actual -> status kualitas yang berlaku -> alokasi SO -> pengiriman customer. Selisih output terhadap forecast tetap fakta fisik; keputusan kekurangan/amandemen mengikuti flow existing, tanpa auto-fabrikasi stok. **Catatan:** Belum closure: validator metadata melaporkan 317 hambatan. Ini bukan 317 bug aplikasi; migrasi, UAT dan chain end-to-end belum tuntas. |
| LN-143-T03 | BELUM VALIDASI PENUH | Receipt parsial campuran supplier dan makloon pada satu Pesanan Khusus tidak membuat seluruh pesanan ready; panel tracking/pengiriman bekerja tanpa linked_po_id untuk jalur makloon dan menampilkan semua dokumen yang relevan. **Catatan:** Belum closure: validator metadata melaporkan 317 hambatan. Ini bukan 317 bug aplikasi; migrasi, UAT dan chain end-to-end belum tuntas. |
| LN-143-T04 | BELUM VALIDASI PENUH | Dua Pesanan Khusus untuk SKU dan entitas sama menerima hasil berbeda: receipt/QC ditautkan dengan dokumen dan line asal, tidak find_one product_id yang kebetulan cocok. Penerimaan unrelated tidak mengubah status pesanan ini. **Catatan:** Belum closure: validator metadata melaporkan 317 hambatan. Ini bukan 317 bug aplikasi; migrasi, UAT dan chain end-to-end belum tuntas. |
| LN-143-T05 | BELUM VALIDASI PENUH | Receipt dan QC callback diulang atau datang tidak berurutan: stok, alokasi, outbound task dan status tidak ganda. Barang karantina/reject atau teralokasi ke pesanan lain tidak tersedia untuk dikirim. **Catatan:** Belum closure: validator metadata melaporkan 317 hambatan. Ini bukan 317 bug aplikasi; migrasi, UAT dan chain end-to-end belum tuntas. |
| LN-143-T06 | BELUM VALIDASI PENUH | Rekonsiliasi Finance: pembelian output supplier berbeda dari bahan milik sendiri + jasa makloon. Tidak menggandakan inventory/HPP/AP/AR; biaya pengadaan tidak menimpa harga jual Grade A atau Special Price yang disetujui. Bukti mencatat event posting actual dan invariant sebelum/sesudah. **Catatan:** Belum closure: validator metadata melaporkan 317 hambatan. Ini bukan 317 bug aplikasi; migrasi, UAT dan chain end-to-end belum tuntas. |
| LN-143-T07 | BELUM VALIDASI PENUH | Regression SO normal, R&D internal tanpa pesanan, PR manual supplier/makloon, revalidation SKU existing, serta WMS lintas lokasi/entitas tetap berfungsi. Mutasi role/owner/location tidak menjadi jalan pintas pemenuhan. **Catatan:** Belum closure: validator metadata melaporkan 317 hambatan. Ini bukan 317 bug aplikasi; migrasi, UAT dan chain end-to-end belum tuntas. |
| LN-143-T08 | BELUM VALIDASI PENUH | UAT dua jalur pada kandidat final menyertakan navigasi aktual, request/respons, nomor dokumen dan line, qty bahan/output/allocated/shipped, status kualitas, biaya/ledger dan evidence UI. Simulasi plan atau unit test tunggal tidak memenuhi kelulusan rangkaian ini. **Catatan:** Belum closure: validator metadata melaporkan 317 hambatan. Ini bukan 317 bug aplikasi; migrasi, UAT dan chain end-to-end belum tuntas. |
