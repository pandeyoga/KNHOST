"""UAT v3.0 — 16 alur end-to-end LURUS (satu cabang = satu alur utuh, dibaca dari atas ke bawah tanpa melompat).

Struktur SCENARIOS: kode, judul, kapan cabang ini terjadi, kelompok, mulai, menit, peran, data, perbaikan terkait,
status cek UI ("full" / "partial" / "none"), langkah.
"""
import v3_steps as s

KANDA_SALES = ("Sales", "sales.kanda@kainnusantara.id")
KANDA_ADM = "salesadmin.kanda@kainnusantara.id"
WH_RCM = ("Gudang", "warehouse.rancamalang@kainnusantara.id")
CST_ADM = ("CST", "salesadmin.cst@kainnusantara.id")


def _s1():
    return (s.pos_order(tax=True) + s.admin_sales() + s.pick() + s.dispatch() + s.logistics("ekspedisi") +
            s.tax_invoice() + s.pay() + s.journey())


def _s2():
    return (s.pos_order(term="CBD — Bayar Sebelum Kirim", ui="S2",
                        review_hint="Kotak **Pemenuhan** memberi tahu: *Termin CBD wajib dibayar 100% (Rp …) sebelum kirim — "
                                    "pengiriman tertahan sampai Finance mencatat pembayaran*.") +
            s.verify("S2") + s.submit("S2") +
            [("Admin Sales", "antrean **Siap dikonfirmasi** → [[Konfirmasi]]", "Konfirmasi pesanan.",
              "*dikonfirmasi — tugas gudang lahir.* Pelacak SO: tahap berikutnya *Dibayar sesuai termin CBD sebelum kirim — Finance*.", "S2")] +
            s.pick("S2", badge=" + **tertahan bayar**") +
            [("Gudang", "`Barang Keluar` → tugas SO (lencana **TERTAHAN BAYAR · CBD**) → panel kirim",
              "Coba kirim.",
              "Kotak merah *Tertahan — belum dibayar sesuai termin* (wajib Rp …, sudah dibayar Rp 0, kurang Rp …); "
              "[[Kirim Sebagian]] / [[Kirim Semua]] **nonaktif** dengan alasan.", "S2"),
             ("Finance", f"`Meja Finance` ({s.SUKACITA}) → antrean **Menunggu pembayaran sebelum kirim (CBD/DP)** → [[Catat kwitansi]]",
              "Pelanggan sudah transfer. Dialog *Catat Pembayaran*: SO ini di urutan teratas & nominal terisi → [[Simpan Pembayaran]]. "
              "Cara lain: detail SO → kotak termin → [[Catat pembayaran (Rp …)]].",
              "*Pembayaran KSC/AR-xxxxx dicatat*; SO keluar dari antrean; kiriman otomatis terbuka.", "S2"),
             ("Finance / Manajer", "detail SO → kotak termin → [[Beri pengecualian kirim]] (hanya bila belum bayar tapi harus kirim)",
              "Opsional: isi alasan (min. 5 huruf) → [[Simpan pengecualian]]. Dapat dicabut lagi dengan alasan.",
              "*Boleh kirim — pengecualian berizin* + pelaku, waktu, alasan. Gudang & Sales tidak punya tombol ini.", "S2")] +
            s.dispatch("S2", gate="Kotak hijau *Boleh kirim — termin terpenuhi* (sudah dibayar Rp …).") +
            s.logistics("armada", "S2") +
            s.journey("S2", "Uang masuk KSC/AR-xxxxx tampil; tanggal *Dibayar* lebih awal dari *Dikirim*."))


def _s3():
    return (s.pos_order(term="Tunai / POS", fulfil="ambil", ui="",
                        review_hint="Ringkasan *Diambil oleh … · Ambil di gudang · tanggal*.") +
            s.admin_sales() +
            [("Gudang", "`Operasi Gudang › Barang Keluar` → filter **Terjadwal (Ambil)** → tugas SO",
              "Tugas ditahan sampai tanggal ambil. Bila pelanggan datang lebih awal → [[Rilis ke Antrean]] → [[Rilis ke Antrean]] (konfirmasi).",
              "Kotak ungu *Barang baru disiapkan pada/setelah tanggal ambil*; setelah rilis tugas masuk antrean pengambilan.", "")] +
            s.pick() + s.dispatch() +
            [("Admin Gudang", "`Gudang & Logistik › Pengiriman` → [[Buat Pengiriman]] → Jenis **Diambil pelanggan**",
              "Pilih SJ pesanan ini; simpan. Sales memberi **kode pickup** ke pelanggan.",
              "Pengiriman *Menunggu diambil*.", ""),
             ("Admin Gudang", "detail pengiriman → [[Verifikasi & serahkan]]",
              "Pelanggan datang: ketik **kode pickup** + nama & nomor identitas pengambil.",
              "Kode salah → *KODE PICKUP SALAH — barang tidak boleh diserahkan*. Benar → *Diserahkan*; SO *Selesai*.", "")] +
            s.pay(method="Tunai") + s.journey(""))


def _s4():
    return (s.pos_order() + s.sales_so_approval("harga", price="Rp 17.500") +
            s.verify() +
            s.submit(gate_note="SO *Menunggu persetujuan* (*Menunggu approval harga khusus*); pindah ke antrean **Menunggu keputusan manajer**.") +
            [("Manajer", "`Meja Saya` → **Permintaan harga khusus** → [[Putuskan]] (atau `Pusat Persetujuan › Inbox Persetujuan`)",
              "Bandingkan harga normal vs diminta, alasan & bukti → [[Tolak]] + catatan (mis. *margin terlalu tipis*).",
              "Entri *ditolak* + pemutus & catatan.", ""),
             ("Sales", "HP: tab **Pesanan** → ketuk SO → kotak **Persetujuan** → [[Ajukan Harga Khusus]] → [[Ajukan]]",
              "Baca entri **DITOLAK** + *Catatan pemutus*. Nego ulang dengan pelanggan → ajukan harga baru (mis. Rp 19.000) + bukti.",
              "Entri lama *Digantikan pengajuan baru*; entri baru *MENUNGGU*. SO tidak terkunci (F-09).", "HP"),
             ("Manajer", "`Meja Saya` → **Permintaan harga khusus** → [[Putuskan]] → [[Setujui]]",
              "Setujui harga baru + catatan.",
              "Harga baris = harga khusus; subtotal, PPN, grand total dihitung ulang; **SO otomatis Disetujui**.", "")] +
            s.confirm() + s.pick() + s.dispatch() + s.logistics("ekspedisi") +
            s.pay() + s.journey("", "Langkah *Disetujui* mencatat manajer pemutus harga khusus."))


def _s5():
    return ([(KANDA_SALES, "HP: tab **Katalog** → cari *LYFLEX ACTIVE BEIGE A* → [[Pilih]] → qty kg → [[Tambah …]] → tab **Keranjang** → [[Lanjut ke Checkout]]",
              "Langkah 1: pelanggan *CV Garmen Soreang Jaya* (limit kredit **Rp25 jt**). Qty sampai nilai melewati limit "
              "(mis. ±700 kg × Rp41 rb ≈ Rp28,7 jt). Langkah 2: termin *Kredit NET 30 Hari*.",
              "Langkah 3 *Review*: kotak kredit **Peringatan / Terblokir kredit** + alasan, AR vs limit, proyeksi.", ""),
             (KANDA_SALES, "Checkout langkah 3 → [[Buat Sales Order]]", "Buat SO.", "SO terbentuk; kartu SO menandai masalah kredit.", ""),
             (KANDA_SALES, "HP: tab **Pesanan** → ketuk SO → kotak **Persetujuan** → [[Minta Persetujuan Kredit]]",
              "Isi alasan (mis. *pelanggan lama, pembayaran lancar*) → kirim.",
              "Entri *Persetujuan Kredit (Melebihi Batas) · MENUNGGU*; SO *Menunggu approval kredit*.", "")] +
            s.verify("", KANDA_ADM) +
            s.submit("", KANDA_ADM, gate_note="SO *Menunggu persetujuan* (kredit). Approve langsung oleh Admin Sales ditolak.") +
            [("Manajer", "`Pusat Persetujuan › Inbox Persetujuan` (atau `Meja Saya`) → entri kredit → [[Putuskan]] → [[Setujui]]",
              "Tinjau limit, eksposur, umur piutang; isi catatan (mis. *ACC direksi via WA*).",
              "*Credit hold* dilepas, override tercatat terpakai, **SO otomatis Disetujui**.", "")] +
            s.confirm("", KANDA_ADM) +
            s.pick("", account="warehouse.soreang@kainnusantara.id", wh="Soreang · Gudang Kanda") +
            s.dispatch("", entity="Kanda Fabric") + s.logistics("armada", "") +
            s.pay("", entity="Kanda Fabric") + s.journey(""))


def _s6():
    return (s.pos_order(qc="QC seluruh roll", ui="") + s.admin_sales() + s.pick() +
            [("Gudang", "`Barang Keluar` → panel **Siap dikirim** → [[Kirim Semua]]",
              "Coba kirim sebelum QC.",
              "Ditolak: *SO meminta QC … kirim menunggu SPK QC selesai*.", ""),
             ("Admin Gudang", "`Meja Gudang` → antrean **SPK inspeksi belum ditugaskan** → [[Tugaskan]]",
              "Pilih petugas QC, tanggal SPK → simpan.", "SPK *Ditugaskan*; muncul di antrean QC.", ""),
             ("QC", "`Operasi Gudang › QC & Inspeksi` → SPK QC pesanan → [[Mulai diperiksa]]",
              "Per roll: panjang diinspeksi (**yard**) & cacat per interval 15 yd (4-point) → [[Simpan hasil]].",
              "Hasil per roll + grade saran tersimpan.", ""),
             ("Admin Gudang", "SPK → [[Keputusan]] → lulus / tolak per roll → tutup SPK",
              "Satu keputusan SPK. Roll tidak lulus → Admin Sales **Ganti Roll** lalu QC ulang roll pengganti.",
              "SPK *Selesai*; pesan tahan QC hilang dari panel kirim.", "")] +
            s.dispatch() + s.logistics("ekspedisi") + s.pay() + s.journey(""))


def _s7():
    return ([("Sales", "HP: tab **Katalog** → cari *ALICE KNIT (94139-45) 14 A* → [[Pilih]] → qty **100 kg** → tab **Keranjang** → [[Lanjut ke Checkout]]",
              "Langkah 1: pelanggan *Toko Kain Sejahtera*. Langkah 2: aktifkan **backorder** untuk baris yang kurang stok. Langkah 3 → [[Buat Sales Order]].",
              "Tanpa backorder → ditolak *Stok milik entitas tidak mencukupi … Aktifkan backorder*. Dengan backorder → SO "
              "**Menunggu stok**; *Sebagian via backorder (disetujui)*.", "")] +
            s.verify() +
            [("Admin Sales", "`Meja Admin Sales` → antrean **Perlu dipenuhi (kurang stok)** → [[Putuskan pemenuhan]]",
              "Panel menampilkan stok sendiri per gudang, stok di PT lain (+ kesiapan harga internal), PO berjalan, sisa kebutuhan. "
              "Isi **transfer dari PT lain**: *Cipta Sandang* 100 kg → simpan.",
              "Total rencana > kekurangan → ditolak. Tersimpan: *Keputusan pemenuhan*; **Permintaan Internal (PIN)** → "
              "**Transaksi Antar-PT KSC/IC-xxxxx** terbentuk & tertaut ke SO.", ""),
             (CST_ADM, "`Akuntansi & Pajak › Antar Entitas (Grup)` (Kerja di: Cipta Sandang) → transaksi IC → setujui & serahkan",
              "PT pemasok menyerahkan barang lewat dokumen resmi (pemilik roll berpindah ke Sukacita).",
              "Pemilik roll = Sukacita; lokasi fisik masih *Rancamalang · Gudang Knitting*.", ""),
             ("Sistem", "otomatis", "Roll yang sudah milik Sukacita dicadangkan ke SO backorder.",
              "SO kembali **Dicadangkan** untuk qty yang tersedia; antrean *Perlu dipenuhi* berkurang.", "")] +
            s.submit("") + s.confirm("") +
            s.pick("", account=WH_RCM[1], wh="Rancamalang · Gudang Knitting") +
            s.dispatch("") + s.logistics("armada", "") + s.pay("") + s.journey(""))


def _s8():
    return ([("Sales", "HP: tab **Katalog** → *ALICE KNIT 14 A* **100 kg** → Checkout + backorder → [[Buat Sales Order]]",
              "Sama dengan S7 langkah 1.", "SO **Menunggu stok**.", "")] +
            s.verify("") +
            [("Admin Sales", "`Meja Admin Sales` → **Perlu dipenuhi (kurang stok)** → [[Putuskan pemenuhan]]",
              "Isi **PO ke supplier** 100 kg → simpan. Jalankan ulang tidak menggandakan PR.",
              "**Permintaan Pembelian PR-xxxxx** lahir & merujuk SO.", ""),
             ("Pembelian", "`Pembelian › Pengadaan › Permintaan Pembelian` → PR → **Sourcing** → *beli ke supplier* → [[Realisasi]]",
              "Pilih supplier (mis. *PT Kimia Warna Prima*), gudang penerimaan, tanggal kirim.",
              "**PO KSC/PO-xxxxx** + tugas inbound *menunggu barang*; qty PO = *incoming* (bukan stok). PR ≥ Rp50 jt / "
              "PO ≥ Rp100 jt → ACC manajer dulu (`Pusat Persetujuan`).", ""),
             ("Supplier", "di luar sistem", "Supplier mengirim barang + Surat Jalan bernomor PO.", "—", ""),
             ("Admin Gudang", "`Operasi Gudang › Barang Masuk` → [[Buat kedatangan]]",
              "Pilih supplier, gudang penerimaan, PO yang datang. Unggah foto SJ (dibaca otomatis) atau isi manual: nomor & "
              "tanggal SJ, baris barang (qty & unit menurut SJ, jumlah roll) → pilih target PO.",
              "**KSC/GRN-xxxxx** *Draf → Review → Hitung*.", ""),
             ("Gudang", "kedatangan → [[Hitung fisik]] → scan label supplier / [[Cetak label KN roll ini]]",
              "Per roll catat berat (kg) / panjang **fisik**, LOT supplier; tempel label.", "Roll lahir status *receiving*.", ""),
             ("Admin Gudang", "kedatangan → [[Rekonsiliasi]] → [[Tutup Penerimaan]]",
              "Putuskan tiap selisih vs SJ: [[Terima dengan catatan]] / klaim supplier / [[Tolak barang]] + alasan.",
              "Stok bertambah sebesar fisik; PO *Sebagian/Penuh diterima*; roll **karantina**; **SPK inspeksi (INS)** otomatis.", ""),
             ("Admin Gudang", "`Meja Gudang` → **SPK inspeksi belum ditugaskan** → [[Tugaskan]]",
              "Pilih petugas QC & tanggal.", "SPK *Ditugaskan*. MD Quality baru bisa mengisi sesudah ini (F-13).", ""),
             ("MD Quality", "`Operasi Gudang › QC & Inspeksi` → Dokumen Inspeksi → baris roll → **MD Quality**",
              "Bandingkan dengan sample ACC: warna (sesuai / beda shade / tolak), handfeel (skor 1–5); potongan uji dicatat.",
              "Dua indikator tersimpan terpisah.", ""),
             ("QC", "SPK → [[Mulai diperiksa]] → QC 4-point → [[Simpan hasil]]",
              "Panjang inspeksi (yard) & cacat per 15 yd.", "Hasil per roll + grade saran.", ""),
             ("Admin Gudang", "SPK → [[Keputusan]] → terima / terima sebagian / turun grade / tolak",
              "**Satu keputusan** (F-14): roll diterima langsung lepas karantina; roll ditolak → disposisi (rusak / retur ke supplier → Nota Debit).",
              "SPK *Selesai*; roll **tersedia**; sistem mencadangkan ke SO backorder → SO **Dicadangkan**.", "")] +
            s.submit("") + s.confirm("") + s.pick("") + s.dispatch("") + s.logistics("ekspedisi", "") + s.pay("") + s.journey("") +
            [("Finance", "`Pembelian › Hutang Pemasok` → Tagihan Supplier → Kontrabon → `Meja Finance` → **Hutang supplier jatuh tempo** → [[Bayar]]",
              "Cocokkan tagihan supplier dengan penerimaan; tukar faktur; bayar sesuai termin.", "Hutang PO lunas.", "")])


def _s9():
    return ([("Sales", "HP: tab **Katalog** → artikel hasil proses (mis. printing dari greige) → Checkout + backorder → [[Buat Sales Order]]",
              "Pesan qty yang belum ada stok jadinya.", "SO **Menunggu stok**.", "")] +
            s.verify("") +
            [("Admin Sales", "**Perlu dipenuhi (kurang stok)** → [[Putuskan pemenuhan]] → *PO ke supplier* (jalur dipilih Pembelian)",
              "Simpan rencana.", "PR lahir & merujuk SO.", ""),
             ("Pembelian", "`Permintaan Pembelian` → PR → **Sourcing** → *makloon* → Wizard Makloon",
              "Pilih mitra makloon, resep proses, output & unit, bahan/greige yang dipakai. Cetak **SPK Makloon**.",
              "**Order Makloon MKO-xxxxx** (`Pesanan Pembelian › Order Makloon`); bahan *dipesan* (reservasi ≠ pengeluaran).", ""),
             ("Gudang", "`Order Makloon` → pengeluaran bahan",
              "Keluarkan bahan/greige ke mitra sesuai dokumen (sekali).", "Stok bahan keluar tepat sekali; MKO *Diproses mitra*.", ""),
             ("Mitra", "di luar sistem", "Mitra memproses & mengirim hasil + SJ.", "Hasil aktual boleh ≠ rencana (mis. 192 dari 200 yd).", ""),
             ("Admin Gudang", "`Barang Masuk` → [[Buat kedatangan]] (mitra makloon) → SJ → [[Hitung fisik]] → [[Rekonsiliasi]] → [[Tutup Penerimaan]]",
              "Sama dengan S8 langkah kedatangan; target = MKO.",
              "Roll hasil karantina + SPK inspeksi; susut & klaim mitra terlihat di `Rekap Susut & Klaim Mitra`.", ""),
             ("Admin Gudang · QC · MD Quality", "`Meja Gudang` → [[Tugaskan]] SPK → MDQ & QC → [[Keputusan]]",
              "Sama dengan S8 (tugaskan → MD Quality → QC 4-point → satu keputusan).",
              "Roll tersedia & dicadangkan ke SO.", "")] +
            s.submit("") + s.confirm("") + s.pick("") + s.dispatch("") + s.logistics("ekspedisi", "") + s.pay("") + s.journey(""))


def _s10():
    return ([("Sales", "HP: tab **Katalog** → produk woven + knit + printing yang stoknya di **Rancamalang** → Checkout → [[Buat Sales Order]]",
              "Pengiriman ke pelanggan Jakarta.", "SO *Dicadangkan*.", "")] +
            s.admin_sales("") +
            [(WH_RCM, "`Meja Saya` → **Tugas gudang** → satu tugas **per gudang** (Woven / Knitting / Printing) → [[Kerjakan]] → [[Ambil]] → [[Kirim Pengambilan]]",
              "Pick tiap gudang terpisah. Roll gudang lain tidak bisa dipindai ke tugas ini.",
              "Semua tugas *diambil penuh*.", ""),
             (WH_RCM, "`Operasi Gudang › Stok, Transfer & Opname › Transfer` → tujuan **Rancamalang · Gudang Transit**",
              "Transfer internal (pemilik & reservasi tetap); scan serah terima per roll.", "Lokasi fisik pindah ke transit.", ""),
             ("Admin Gudang", "`Gudang & Logistik › Pengiriman` → [[Buat Pengiriman]] (Rancamalang → Jakarta) → Dimuat → Berangkat",
              "Perjalanan internal antargudang, **bukan** pengiriman pelanggan.", "Barang *dalam perjalanan internal*.", ""),
             ("Gudang", "Jakarta: `Barang Masuk` / transfer → terima → scan roll yang turun",
              "Cocokkan dengan yang diberangkatkan; selisih dicatat per roll.", "Roll tiba di Jakarta; reservasi SO tetap.", "")] +
            s.dispatch("") + s.logistics("armada", "") + s.pay("") +
            s.journey("", "Rantai: SO → pick per gudang → transit → terima Jakarta → SJ pelanggan → POD."))


def _sample(paid):
    rows = [("Sales", "HP: tab **Katalog** → kartu produk → [[Pilih]] → **Order sample**",
             "Pilih jenis **Standar** (woven ≤ 5 yd, knit ≤ 2 kg) / **Hanger** (≤ 0,5 yd) / **Catalogue**; qty → [[Tambah ke Keranjang]]. "
             "Sample tidak bisa dicampur baris biasa.",
             "Keranjang *ORDER SAMPLE*; melebihi batas → ditolak (*jual sebagai ECER berbayar*).", ""),
            ("Sales", "tab **Keranjang** → [[Lanjut ke Checkout]] → pilih **" + ("Berbayar" if paid else "Gratis") + "** → langkah 3: *Disesuaikan Admin Sample* / *Pilih tanggal* → [[Buat]]",
             "Tanggal kirim sample boleh diserahkan ke Admin Sample.",
             "Nomor **KSC/SOS-xxxxx** (terpisah dari SO); harga " + ("dari master harga sample." if paid else "tampil *Free*."), "")]
    if paid:
        rows.append(("Finance", "`Penjualan › Pesanan Sample` / `Meja Sample` → **Sample berbayar — menunggu persetujuan pembayaran** → [[Setujui Bayar]]",
                     "Pastikan pembayaran / kesepakatan bayar ada; catatan → setujui (Admin Sample juga berwenang).",
                     "SOS *Disetujui*. Sales → tidak punya tombol; teruskan sebelum disetujui → ditolak.", ""))
    rows += [("Admin Sample", "`Meja Sample` → **Siap diteruskan ke gudang** → [[Teruskan ke Gudang]]",
              "Teruskan; catalogue boleh ganti warna *soft* (berjejak).", "Tugas potong sample lahir di gudang.", ""),
             ("Gudang", "`Meja Saya` → **Sample untuk dipotong** → [[Kerjakan]] → `Barang Keluar` → panel potong sample",
              "Scan roll induk, potong, catat **panjang aktual**.",
              "Roll anak tertaut induk; nilai SOS mengikuti panjang aktual. Roll produk lain → ditolak.", "")]
    if paid:
        rows.append(("Admin Sample", "`Meja Sample` → antrean bayar sample (bila nilai aktual berubah > ±5%)",
                     "Selisih ≤ ±5% → tagihan menyesuaikan otomatis. Di atas 5% → **persetujuan ulang** pembayaran (F-15).",
                     "Status persetujuan ulang tampil; kirim tertahan sampai disetujui.", ""))
    rows += [("Admin Sample", "`Meja Sample` → terima hasil potong (serah terima Admin Cutting)",
              "Terima potongan dari gudang.", "Kirim sebelum diterima → ditolak *belum diterima Admin Cutting*.", ""),
             ("Gudang", "`Barang Keluar` → tugas sample → [[Kirim Semua]] → [[Kirim Sekarang]]",
              "Kirim sample (Admin Gudang override cek muat bila tanpa RFID — seperti S1).", "SJ sample terbit; SOS *Dikirim*.", "")]
    rows += s.logistics("ekspedisi", "")
    if paid:
        rows += [("Finance", "`Meja Finance` → **Uang masuk** → [[Catat kwitansi]] atas nilai **aktual**",
                  "Catat pembayaran sample.", "SOS lunas.", "")]
    rows += [("Sales", "HP: tab **Lainnya** › **Pesanan Sample** → ketuk SOS", "Periksa status akhir.",
              "SOS *Selesai*" + (" & lunas." if paid else " (tanpa tagihan)."), "")]
    return rows


def _s13():
    return [
        ("Sales", "HP: tab **Lainnya** › **Pesanan Khusus (OD)** → [[Ajukan pesanan khusus]]",
         "Bagian 1: pelanggan, judul permintaan. Bagian 2: **Item 1** = A 100 yd (sumber *Induk produk (custom warna)*), "
         "[[Tambah item]] **Item 2** = B 200 yd (sumber *Referensi / desain pelanggan*); jenis uji Printing / Labdip / Handfeel; satuan.",
         "Formulir 6 bagian; pesan *Belum lengkap: …* menyebut isian yang kurang.", ""),
        ("Sales", "formulir OD → bagian 3–6 → centang *Langsung ajukan untuk persetujuan Manajer* → [[Simpan pesanan khusus]]",
         "Referensi pelanggan, warna target, foto swatch (opsional), **tenggat kirim**, catatan.",
         "**SORD-yymmdd-xxxx** *Menunggu persetujuan*.", ""),
        ("Manajer", "`Pusat Persetujuan` / detail OD → [[Setujui]]", "Rantai persetujuan berjenjang.",
         "OD *Disetujui* → otomatis **Permintaan Desain (DSR)** untuk printing & **Permintaan Sample R&D** untuk labdip/handfeel.", ""),
        ("MD", "`Desainer › Permintaan Desain` → [[Tugaskan]]", "Pilih desainer & tenggat.", "DSR *Ditugaskan*.", ""),
        ("Desainer", "`Meja Saya › Desain yang saya kerjakan` → [[Kerjakan]] → unggah artwork → centang **Print paper** → [[Ajukan untuk review]]",
         "Kerjakan artwork ronde ini.", "*Menunggu keputusan*; versi & checklist per ronde.", ""),
        ("PIC", "DSR → [[Mulai review]] → [[Setujui (ACC) + nilai akhir]]",
         "ACC dengan nilai desain (revisi: [[Minta revisi]] + alasan → kembali ke desainer).",
         "Sample proofing lahir otomatis; MD diberi tahu.", ""),
        ("R&D", "`R&D › Permintaan Sample` → detail → [[Kirim Permintaan ke Supplier]]",
         "Periksa spesifikasi (diwarisi OD), pilih supplier peserta & jenis uji wajib lini.", "Permintaan *Terkirim*.", ""),
        ("R&D", "Permintaan Sample → [[Catat Pengiriman Sample]] → [[Nilai]] → [[Pilih supplier pemenang]] → [[Tandai Sample Jadi]]",
         "Catat sample datang, nilai per jenis, pilih pemenang.", "OD fase *Sample siap*.", ""),
        ("Sales", "HP: tab **Lainnya** › **Pesanan Khusus (OD)** → ketuk OD → [[Kirim ke Pelanggan]]", "Kirim sample fisik ke pelanggan.", "OD *Menunggu ACC pelanggan*.", ""),
        ("Admin Sales", "`Meja Admin Sales` → **Pesanan khusus — menunggu ACC pelanggan** → [[Catat ACC]]",
         "Catat keputusan pelanggan **ACC** + tanggal, catatan, bukti (foto/WA).", "OD lanjut ke kunci harga.", ""),
        ("Admin Sales", "`Meja Admin Sales` → **Pesanan khusus — perlu kunci harga** → [[Kunci harga]]",
         "Harga = harga supplier pemenang + margin (bawaan 30%).", "Harga terkunci per item; **PR/PO** ke supplier pemenang lahir.", ""),
        ("MD", "detail OD → [[Buat SKU]]", "SKU baru tertaut induk & item; eksklusif pelanggan pemilik OD.", "SKU aktif.", ""),
        ("Pembelian · Admin Gudang · QC", "PR → [[Realisasi]] PO → `Barang Masuk` kedatangan → hitung → tutup → SPK → keputusan",
         "Sama dengan S8 bagian pengadaan & kedatangan.", "Stok item OD tersedia.", ""),
        ("Admin Sales", "detail OD → [[Ubah ke Pesanan Penjualan]]",
         "Konversi item A & B (SKU, unit, harga terkunci).", "**SO** tertaut OD; ulang tidak membuat SO kedua.", ""),
    ] + s.verify("") + s.submit("") + s.confirm("") + s.pick("") + s.dispatch("") + s.logistics("ekspedisi", "") + s.pay("") + \
        s.journey("", "OD ikut *Dikirim* lalu *Selesai*.")


def _retur_front():
    return [
        ("Sales", "HP: tab **Pesanan** → ketuk SO yang sudah Selesai (mis. dari S1) → [[Ajukan retur]] (atau **Lainnya** › **Retur Penjualan** → [[Buat retur jual]])",
         "Daftar roll yang benar-benar terkirim tampil otomatis. Pilih roll & qty klaim, kondisi, **sebab keluhan**, catatan, foto → ajukan.",
         "**SRET-xxxxx** *Menunggu persetujuan*. Klaim > 21 hari dari SJ → ditolak / [[Ajukan pengecualian]].", ""),
        ("Manajer", "`Meja Saya` → **Retur menunggu ACC** → [[Putuskan]] → [[Setujui]]",
         "Setujui barang kembali untuk diperiksa (bukan keputusan refund/tukar).", "Retur *Disetujui*.", ""),
        ("Gudang", "detail retur → **Perjalanan Retur** → [[Terima di gudang]] → pilih *Jakarta* → scan → [[Catat scan]]",
         "Terima roll retur di Jakarta.", "Posisi fisik per roll tercatat; belum jadi stok jual. (F-11: Gudang kini bisa membuka & memproses.)", ""),
        ("Gudang", "Perjalanan Retur → [[Kirim ke gudang lain (dalam perjalanan)]] → tujuan *Rancamalang · Gudang Transit*",
         "Pilih kurir/armada.", "Status *dalam perjalanan*.", ""),
        (WH_RCM, "Perjalanan Retur → [[Tiba di gudang tujuan]] → scan", "Cocokkan roll.", "Roll di area transit menunggu QC.", ""),
        ("QC", "detail retur → panel **Inspeksi** → mulai → isi hasil → [[Selesai Inspeksi]]",
         "Per roll: qty aktual, kondisi, cacat 4-point, grade.",
         "Retur *Selesai inspeksi*. QC sebelum barang diterima → ditolak (F-12).", ""),
    ]


def _s14():
    return _retur_front() + [
        ("MD Quality", "detail retur → panel **Cutloss** (opsional)",
         "Catat qty cacat (yard) + posisi; pecah roll: potongan baik dikirim kembali, potongan cacat → BS / dibuang.",
         "Roll anak berurutan; potongan BS tercatat.", ""),
        ("Finance", "detail retur → panel **Kompensasi** → nilai → **Catatan keputusan Finance (wajib)** → [[Selesaikan]]",
         "Nilai = harga transaksi awal × qty disetujui; diskon = nominal per item untuk qty cacat.", "Kompensasi *diputus*; dasar hitung terlihat.", ""),
        ("Manajer", "detail retur → [[Selesaikan]] → outcome **Refund** / **Store credit** / **Nego**",
         "Isi bukti keputusan (mis. *ACC Pak Budi via WA*) + lampiran; pilih gudang retur.",
         "Retur *refund_settled / credit_settled / nego_settled*. Admin Sales tidak bisa (403).", ""),
        ("Finance", "`Keuangan › Saldo Kredit` / `Kas & Bank` / `Meja Finance`",
         "SO asal belum lunas → potong tagihan dulu; sudah lunas → refund atau saldo sesuai pilihan pelanggan.",
         "Saldo pelanggan & piutang benar; satu posting.", ""),
        ("Admin Sales", "detail retur → **Tujuan barang retur** → per roll [[Simpan sebagai stok]] / kembalikan ke PT pemasok",
         "Putuskan nasib roll hasil QC.", "Roll tersimpan dengan grade/hold hasil QC (bukan otomatis tersedia).", ""),
    ]


def _s15():
    return _retur_front() + [
        ("Manajer", "detail retur → [[Selesaikan]] → outcome **Tukar**", "Isi bukti keputusan.", "Retur menunggu pesanan pengganti.", ""),
        ("Admin Sales", "detail retur → **Pesanan pengganti** → [[Buat pesanan pengganti]]",
         "Artikel/warna/grade sama; qty = yard aktual hasil QC. Selisih lebih → dibayar pelanggan; kurang → refund/saldo.",
         "**SO pengganti** tertaut retur; roll yang diretur tidak boleh dikirim lagi ke pelanggan asal.", ""),
    ] + s.verify("") + s.submit("") + s.confirm("") + s.pick("") + s.dispatch("") + s.logistics("ekspedisi", "") + \
        s.journey("", "SO pengganti selesai; selisih nilai (bila ada) tertagih / dikembalikan.")


def _s16():
    return [
        ("Pembelian", "`Pembelian › Pengadaan › Saran Reorder` → pilih artikel → buat **Permintaan Pembelian**",
         "Restock artikel yang di bawah titik pesan ulang.", "PR-xxxxx (≥ Rp50 jt → ACC manajer).", ""),
        ("Manajer", "`Pusat Persetujuan › Inbox Persetujuan` → PR → [[Setujui]] (bila di atas ambang)", "ACC PR.", "PR *Disetujui*.", ""),
        ("Pembelian", "PR → **Sourcing** → *beli ke supplier* → [[Realisasi]]",
         "Supplier, gudang penerimaan, tanggal kirim.", "**PO KSC/PO-xxxxx** (≥ Rp100 jt → ACC manajer).", ""),
        ("Supplier", "di luar sistem", "Barang + SJ supplier (mis. 10 roll, SJ 1.000 yd, fisik 960 yd).", "—", ""),
        ("Admin Gudang", "`Operasi Gudang › Barang Masuk` → [[Buat kedatangan]] → foto/entri SJ",
         "Isi kepala SJ & baris; target PO.", "GRN *Draf → Review → Hitung*.", ""),
        ("Gudang", "[[Hitung fisik]] per roll → label", "Catat fisik (960 yd).", "Roll *receiving*.", ""),
        ("Admin Gudang", "[[Rekonsiliasi]] → putuskan selisih 40 yd → [[Tutup Penerimaan]]",
         "[[Terima dengan catatan]] atau klaim supplier.", "Stok +960 yd; PO *Sebagian diterima* (sisa incoming); roll karantina + SPK.", ""),
        ("Admin Gudang · MD Quality · QC", "`Meja Gudang` → [[Tugaskan]] SPK → MD Quality → QC 4-point → [[Keputusan]]",
         "Sama dengan S8.", "Roll **tersedia** sekali keputusan.", ""),
        ("Gudang", "`Operasi Gudang › Stok, Transfer & Opname` / `Lokasi Rak` → putaway", "Simpan roll ke rak/bin.",
         "Saldo per gudang/bin benar; roll muncul di katalog POS.", ""),
        ("Finance", "`Pembelian › Hutang Pemasok` → Tagihan Supplier (dari GR) → Kontrabon → `Meja Finance` → **Hutang supplier jatuh tempo** → [[Bayar]]",
         "Tagihan = qty diterima (960 yd), bukan qty SJ.", "Hutang PO lunas; jurnal terposting.", ""),
    ]


# kode, judul, kapan terjadi, kelompok, mulai, menit, peran, data, perbaikan, status cek UI, langkah
SCENARIOS = [
    ("S1", "Penjualan biasa · stok ada · kirim ekspedisi · NET 30 → lunas",
     "Pesanan paling umum: stok PT sendiri cukup, dikirim lewat ekspedisi, pelanggan minta Faktur Pajak, bayar tempo 30 hari.",
     1, "09.15", 45, "Sales · Admin Sales · Gudang · Admin Gudang · Finance", "Toko Kain Sejahtera · CERUTY PREMIUM (yard)",
     "F-01 F-03 F-05 F-06 F-07 F-08 F-16", "full", _s1),
    ("S2", "Termin CBD (bayar sebelum kirim) · armada sendiri → lunas",
     "Pelanggan wajib bayar penuh sebelum barang keluar. Gudang boleh menyiapkan, tetapi kirim terkunci sampai Finance mencatat pembayaran.",
     1, "10.00", 35, "Sales · Admin Sales · Gudang · Finance · Admin Gudang", "Toko Kain Sejahtera · termin CBD",
     "F-10", "full", _s2),
    ("S3", "Ambil sendiri di gudang · bayar tunai",
     "Pelanggan mengambil barang sendiri pada tanggal ambil; serah terima memakai kode pickup.",
     1, "10.35", 30, "Sales · Admin Sales · Gudang · Admin Gudang · Finance", "Toko Kain Sejahtera · termin Tunai",
     "—", "partial", _s3),
    ("S4", "Harga khusus ditolak → diajukan ulang → disetujui",
     "Pelanggan menawar di bawah harga. Manajer menolak pengajuan pertama, Sales nego ulang, pengajuan kedua disetujui.",
     1, "11.05", 40, "Sales · Admin Sales · Manajer · Gudang · Admin Gudang · Finance", "Toko Kain Sejahtera",
     "F-09", "partial", _s4),
    ("S5", "Kredit melewati limit → disetujui manajer",
     "Nilai pesanan membuat piutang pelanggan melewati limit kredit; pesanan baru jalan setelah manajer setuju.",
     1, "11.45", 35, "Sales (Kanda) · Admin Sales (Kanda) · Manajer · Gudang Soreang · Admin Gudang · Finance",
     "CV Garmen Soreang Jaya (limit Rp25 jt) · LYFLEX ACTIVE BEIGE (kg)", "F-09", "none", _s5),
    ("S6", "Pelanggan minta QC sebelum kirim",
     "Barang wajib lulus QC per roll sebelum boleh dikirim.",
     1, "13.20", 40, "Sales · Admin Sales · Gudang · Admin Gudang · QC · Finance", "Toko Kain Sejahtera",
     "F-14", "partial", _s6),
    ("S7", "Stok kurang → dipenuhi dari PT lain (antar-PT)",
     "Stok Sukacita tidak cukup; kekurangan diambil dari Cipta Sandang lewat transaksi antar-PT.",
     1, "14.00", 50, "Sales · Admin Sales · CST · Gudang Rancamalang · Admin Gudang · Finance", "ALICE KNIT 14 A (kg, stok CST)",
     "F-05", "none", _s7),
    ("S14", "Retur → kompensasi (refund / saldo / nego)",
     "Pelanggan komplain barang; setelah diterima & di-QC, diselesaikan dengan uang kembali, saldo, atau diskon.",
     1, "15.05", 45, "Sales · Manajer · Gudang Jakarta & Rancamalang · QC · MD Quality · Finance · Admin Sales", "SO dari S1 (sudah Selesai)",
     "F-11 F-12 F-17", "none", _s14),
    ("S15", "Retur → barang pengganti",
     "Komplain diselesaikan dengan mengirim barang pengganti sampai diterima.",
     1, "15.50", 40, "Sales · Manajer · Gudang · QC · Admin Sales · Admin Gudang", "SO dari S1",
     "F-11 F-12", "none", _s15),
    ("S8", "Stok kurang → PO supplier → kedatangan → SPK → kirim",
     "Kekurangan dibeli dari supplier; barang datang, dihitung, diinspeksi, lalu otomatis dicadangkan ke SO.",
     2, "09.15", 75, "Sales · Admin Sales · Pembelian · Admin Gudang · Gudang · MD Quality · QC · Finance", "ALICE KNIT 14 A · supplier dari master",
     "F-13 F-14", "none", _s8),
    ("S9", "Stok kurang → makloon (proses di mitra)",
     "Barang jadi dibuat dari bahan sendiri oleh mitra makloon, lalu diterima & dikirim ke pelanggan.",
     2, "10.30", 60, "Sales · Admin Sales · Pembelian · Gudang · Admin Gudang · QC · Finance", "artikel printing · mitra makloon dari master",
     "F-13 F-14", "none", _s9),
    ("S10", "Multi-gudang Rancamalang → transit → Jakarta → pelanggan",
     "Satu pesanan diambil dari beberapa gudang Rancamalang, dikumpulkan di transit, dibawa ke Jakarta, lalu dikirim ke pelanggan.",
     2, "11.30", 40, "Sales · Admin Sales · Gudang Rancamalang & Jakarta · Admin Gudang · Finance", "produk woven + knit + printing Rancamalang",
     "F-05", "none", _s10),
    ("S11", "Sample gratis",
     "Pelanggan minta potongan contoh tanpa biaya.",
     2, "13.20", 25, "Sales · Admin Sample · Gudang · Admin Gudang", "Toko Kain Sejahtera", "F-03", "none", lambda: _sample(False)),
    ("S12", "Sample berbayar",
     "Potongan contoh dibayar pelanggan; harga mengikuti panjang aktual (persetujuan ulang bila berubah > ±5%).",
     2, "13.45", 35, "Sales · Finance · Admin Sample · Gudang · Admin Gudang", "Toko Kain Sejahtera", "F-15", "none", lambda: _sample(True)),
    ("S13", "Pesanan Khusus (desain/warna baru) → SO → lunas",
     "Produk belum ada: desain, sample R&D, ACC pelanggan, kunci harga, pengadaan, lalu menjadi SO biasa sampai lunas.",
     2, "14.20", 75, "Sales · Manajer · MD · Desainer · PIC · R&D · Admin Sales · Pembelian · Gudang · Finance", "OD 2 item (A 100 yd, B 200 yd)",
     "—", "none", _s13),
    ("S16", "Pembelian stok (restock) → hutang supplier lunas",
     "Restock rutin dari saran reorder sampai tagihan supplier dibayar; selisih SJ vs fisik diputuskan.",
     2, "15.35", 45, "Pembelian · Manajer · Admin Gudang · Gudang · MD Quality · QC · Finance", "supplier · SJ 1.000 yd vs fisik 960 yd",
     "F-14", "none", _s16),
]
