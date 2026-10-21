"""Alur A — Penjualan normal (Order-to-Cash), stok tersedia."""
from diagram import Diagram

R, G = "#B91C1C", "#15803D"


def a1():
    d = Diagram(["cust", "sales", "sys"], 8, lane_h={"cust": 66, "sales": 84, "sys": 66})
    d.n("a01", "cust", 0, "task", "Minta kain: artikel, warna, qty, kirim/ambil", "A01")
    d.n("a02", "sales", 1, "task", "POS: pilih pelanggan & alamat", "A02")
    d.n("dj", "sales", 2, "decision", "Jenis pesanan?")
    d.n("lE", "cust", 2, "link", "E")
    d.n("lF", "sys", 2, "link", "F")
    d.n("a03", "sales", 3, "task", "Tambah produk: qty atau beli per roll", "A03")
    d.n("a04", "sales", 4, "task", "Genapkan ke roll utuh (opsional)", "A04")
    d.n("a05", "sales", 5, "task", "Termin bayar · QC · tim sales", "A05")
    d.n("dh", "sales", 6, "decision", "Harga nego?")
    d.n("lB", "cust", 6, "link", "B")
    d.n("a06", "sales", 7, "task", "Review → Buat Sales Order", "A06")
    d.n("so", "sys", 7, "doc", "SO · Dicadangkan")
    d.n("ck", "sys", 5, "auto", "Cek stok, lot, kredit, ambang nilai", "A07", w=150)
    d.e("a01", "a02", fs_="b", ts="l")
    d.e("a02", "dj")
    d.e("dj", "a03", "Biasa")
    d.e("dj", "lE", "Sample", fs_="t", ts="b")
    d.e("dj", "lF", "Khusus", fs_="b", ts="t")
    d.e("a03", "a04")
    d.e("a04", "a05")
    d.e("a05", "dh")
    d.e("dh", "a06", "tidak")
    d.e("dh", "lB", "ya", fs_="t", ts="b", color=R)
    d.e("a06", "so", fs_="b", ts="t")
    d.e("so", "ck", fs_="l", ts="r")
    return d


A1_ROWS = [
    ("A01", "Pelanggan", "—", "Pelanggan menyampaikan kebutuhan: artikel, warna, qty + satuan (yard/kg), kirim atau ambil sendiri, perlu QC, perlu Faktur Pajak.",
     "Kebutuhan custom (motif/warna baru) → **Alur F**. Minta potongan contoh → **Alur E**.",
     "Sales mencatat kebutuhan sebagai acuan uji (qty diminta, unit).", "INFO data acuan"),
    ("A02", "Sales", "`Penjualan › POS` → panel **Pelanggan**",
     "Pilih pelanggan *Toko Kain Sejahtera · CUST-0001* dan alamat kirim. Pelanggan baru: [[Pelanggan Baru]].",
     "Pelanggan nonaktif / sudah digabung → ditolak. Badan usaha grup tidak boleh jadi pelanggan SO.",
     "Banner sumber harga muncul (harga langganan → harga PT → harga global). Alamat & penerima terisi.", "OK KSC/SO-00038"),
    ("A03", "Sales", "`POS` → katalog → [[Tambah]] / [[Pilih Varian & Detail]]",
     "Cari artikel (mis. DENIM TENCEL TAUPE), pilih warna, isi qty & satuan, atau mode **Beli per roll** (pilih roll eksplisit). Keranjang menunjukkan jenis: *ORDER BIASA (PO) — nomor SO*.",
     "Ingin sample → [[Kosongkan untuk ganti jenis]] → Order Sample (**E**). Sample tidak boleh dicampur baris biasa.",
     "Harga per satuan benar; Sales **tidak melihat grade, LOT, pemilik entitas**. Stok yang ditampilkan = stok global (pemenuhan diatur Admin Sales).",
     "BUG F-03 grade/LOT bocor di API; F-02 '0 roll tersedia' dari strip *Sering dibeli*"),
    ("A04", "Sales", "`Checkout › Termin & Lot` → **Genapkan ke Roll Utuh**",
     "Bila qty tidak pas roll: buka opsi genapkan, sampaikan ke pelanggan pilihan ke atas / ke bawah / potong; klik [[Pakai Opsi Ini]].",
     "Pelanggan memilih: **atas** (qty naik), **bawah** (qty turun), **potong** (roll terakhir dipotong → reservasi potong di gudang).",
     "Qty final = pilihan pelanggan; daftar roll & total dapat dijelaskan. Tidak ada pembulatan diam-diam.", "NA uji di UI saat UAT"),
    ("A05", "Sales", "`Checkout › Termin & Lot`",
     "Isi qty final; pilih **Termin Pembayaran** (Tunai · CBD · DP 50% · NET 7/14/30/60/90 · Bertahap 3x); **Tim Sales & bagi insentif**; **Request QC sebelum kirim**: Tanpa QC / QC seluruh roll / QC sampling.",
     "Harga di bawah pricelist / hasil nego → [[Minta Harga Khusus]] di kartu item (**Alur B**). Diskon manual tidak tersedia.",
     "Termin tersimpan; bila pilih QC, gudang tidak bisa kirim sebelum QC lulus.", "OK termin, QC (KSC/SO-00043)"),
    ("A06", "Sales", "`Checkout › Review` → [[Buat Sales Order]]",
     "Pilih **Metode Pemenuhan**: Kirim (tanggal kirim opsional, tidak boleh lewat) atau **Ambil di Gudang** (wajib tanggal ambil). Centang **Minta Faktur Pajak** bila perlu. Periksa Subtotal, PPN 12% (DPP 11/12 = efektif 11%), Grand Total.",
     "Ambil tanpa tanggal → ditolak. Qty nol / min. potong tidak terpenuhi → ditolak.",
     "Nomor **KSC/SO-xxxxx** terbit, status **Dicadangkan**; roll dicadangkan 3 hari; pesan Kredit OK / peringatan kredit tampil.",
     "OK SO-00038 150 yd = Rp4.162.500 (PPN 412.500)"),
    ("A07", "Sistem", "otomatis saat SO dibuat",
     "Sistem memeriksa: stok milik entitas penjual, lot campur (minta konfirmasi), limit & tunggakan kredit, ambang nilai (Aturan Persetujuan), pemakaian stok cadangan makloon.",
     "Stok kurang tanpa izin backorder → ditolak; dengan izin → **Alur C**. Kredit/harga/nilai/makloon → entri persetujuan (**Alur B**).",
     "Sub-status menjelaskan alasan berhenti: *Menunggu validasi admin / approval harga / approval kredit / Menunggu stok*.",
     "OK stok kurang 409; kredit KANDA/SO-00007"),
]


def a2():
    d = Diagram(["sales", "sadm", "mgr", "sys"], 8, lane_h={"sales": 64, "sadm": 82, "mgr": 74, "sys": 88})
    d.n("so", "sys", 0, "doc", "SO · Dicadangkan")
    d.n("a08", "sadm", 1, "task", "Meja Admin Sales: Verifikasi kelengkapan", "A08")
    d.n("dv", "sadm", 2, "decision", "Lengkap?")
    d.n("fix", "sales", 2, "task", "Lengkapi alamat / termin (Edit SO)", "A08b")
    d.n("a09", "sadm", 3, "task", "Ajukan persetujuan", "A09")
    d.n("dg", "sys", 4, "decision", "Ada gerbang?")
    d.n("g", "mgr", 4, "gate", "ACC manajer: nilai · kredit · harga", "A10")
    d.n("dk", "mgr", 5, "decision", "Keputusan?")
    d.n("lB", "mgr", 6, "link", "B")
    d.n("ok", "sys", 6, "auto", "SO Disetujui · roll dikunci", w=120)
    d.n("a11", "sadm", 6, "task", "Konfirmasi pesanan", "A11")
    d.n("task", "sys", 7, "doc", "Tugas gudang per gudang")
    d.n("lA3", "sadm", 7, "link", "A3")
    d.e("so", "a08", fs_="t", ts="l")
    d.e("a08", "dv")
    d.e("dv", "fix", "tidak", fs_="t", ts="b", color=R)
    d.e("fix", "a08", fs_="l", ts="t", style="dash")
    d.e("dv", "a09", "ya")
    d.e("a09", "dg", fs_="b", ts="t", via=[(d.nodes["a09"]["cx"], 230)])
    d.e("dg", "g", "ya", fs_="t", ts="b")
    d.e("dg", "ok", "tidak (auto)", fs_="b", ts="b", color=G)
    d.e("g", "dk")
    d.e("dk", "lB", "tolak", color=R)
    d.e("dk", "ok", "setuju", fs_="b", ts="l", via=[(d.nodes["dk"]["cx"], d.nodes["ok"]["cy"])], color=G)
    d.e("ok", "a11", fs_="t", ts="b")
    d.e("a11", "task", fs_="r", ts="t")
    d.e("a11", "lA3")
    return d


A2_ROWS = [
    ("A08", "Admin Sales", "`Meja Admin Sales` → antrean **Perlu diverifikasi** → [[Verifikasi]]",
     "Buka dialog **Verifikasi Kelengkapan**: alamat & nama penerima & telepon, syarat bayar, isi pesanan (qty > 0), perlakuan PPN sesuai PKP, NPWP bila minta faktur, status kredit. Isi catatan → [[Verifikasi sekarang]].",
     "Ada cacat **blokir** → verifikasi ditolak dengan daftar yang harus dilengkapi. Peringatan (NPWP/kredit) tidak memblokir.",
     "SO bertanda **Terverifikasi Admin Sales** (nama & waktu). Riwayat status mencatat *verified_by_sales_admin*.", "OK verifikasi ditolak bila belum, lalu lolos"),
    ("A08b", "Sales", "`Penjualan › Pesanan › Pesanan (SO)` → detail → Edit; atau Admin Sales [[Edit / Override SO]]",
     "Lengkapi data yang kurang (alamat penerima, telepon, termin) lalu kembali ke A08.", "—",
     "Perubahan tercatat di riwayat dengan alasan.", "OK override qty (KSC/SO-00039)"),
    ("A09", "Admin Sales", "detail SO → [[Ajukan persetujuan]]",
     "Mengajukan SO ke gerbang persetujuan. Bila tidak ada gerbang aktif, sistem menyetujui otomatis.",
     "Konfigurasi saat ini: **tanpa** ambang nilai (`sales.require_so_validation` = mati). Gerbang hanya muncul untuk harga khusus, kredit, stok makloon, atau ambang yang dipasang owner.",
     "Status **Disetujui** (otomatis) atau **Menunggu persetujuan** + peran yang dibutuhkan.", "OK auto-approve SO-00038"),
    ("A10", "Manajer", "`Pusat Persetujuan › Inbox Persetujuan` atau `Meja Saya` → **Pesanan penjualan menunggu ACC** → [[Putuskan]]",
     "Baca alasan gerbang (nilai/kredit/harga/makloon), bukti lampiran, ringkasan SO. Putuskan per entri: [[Setujui]] / [[Tolak]] + catatan.",
     "**Tolak** → kembali ke Sales/Admin Sales (Alur B). Sales/Admin Sales **tidak bisa** menyetujui (403). Pengaju harga tidak boleh memutus pengajuannya sendiri.",
     "Bila semua entri disetujui → SO otomatis **Disetujui**, roll berubah *committed*.", "OK 403 untuk Sales & Admin Sales"),
    ("A11", "Admin Sales", "`Meja Admin Sales` → **Siap dikonfirmasi** → [[Konfirmasi]]",
     "Konfirmasi SO yang sudah disetujui. Ini wewenang Admin Sales (tidak perlu manajer).",
     "Konfirmasi sebelum verifikasi → ditolak (409). Sebelum disetujui → ditolak. Konfirmasi ulang → ditolak, tidak membuat tugas ganda.",
     "Status **Dikonfirmasi** (*Siap pick*). **Tugas gudang lahir per gudang & produk**; antrean gudang menerima notifikasi.", "OK 409 urutan & ulang"),
]


def a3():
    d = Diagram(["wh", "whadm", "qc", "sys"], 9, lane_h={"wh": 86, "whadm": 70, "qc": 66, "sys": 70})
    d.n("t", "sys", 0, "doc", "Tugas gudang")
    d.n("a12", "wh", 1, "task", "Meja Saya: Kerjakan · cetak picking list", "A12")
    d.n("dc", "wh", 2, "decision", "Ada reservasi potong?")
    d.n("a13", "wh", 3, "task", "Potong roll induk → roll anak + label", "A13")
    d.n("a14", "wh", 4, "task", "Scan pick tiap roll (ID / RFID)", "A14")
    d.n("dq", "sys", 5, "decision", "SO minta QC?")
    d.n("qc", "qc", 5, "task", "SPK QC pesanan: 4-point per roll", "A15", dy=0)
    d.n("a16", "wh", 6, "task", "Final Loading Check (scan muatan)", "A16")
    d.n("dl", "wh", 7, "decision", "Cocok?")
    d.n("exc", "whadm", 7, "gate", "Pengecualian berizin (tanpa tag)", "A16b")
    d.n("a17", "wh", 8, "task", "Kirim (dispatch)", "A17")
    d.n("sj", "sys", 8, "doc", "Surat Jalan (SJ)")
    d.e("t", "a12", fs_="t", ts="l")
    d.e("a12", "dc")
    d.e("dc", "a13", "ya")
    d.e("dc", "a14", "tidak", fs_="t", ts="t", ym=14)
    d.e("a13", "a14")
    d.e("a14", "dq", fs_="b", ts="l", via=[(d.nodes["a14"]["cx"], d.nodes["dq"]["cy"])])
    d.e("dq", "qc", "ya", fs_="t", ts="b")
    d.e("qc", "a16", "lulus", fs_="t", ts="l", via=[(d.nodes["qc"]["cx"], d.nodes["a16"]["cy"])], color=G)
    d.e("dq", "a16", "tidak", fs_="r", ts="b", via=[(d.nodes["a16"]["cx"], d.nodes["dq"]["cy"])])
    d.e("a16", "dl")
    d.e("dl", "a17", "ya", color=G)
    d.e("dl", "exc", "selisih", fs_="b", ts="t", color=R)
    d.e("exc", "a17", fs_="r", ts="b", style="dash")
    d.e("a17", "sj", fs_="b", ts="t")
    return d


A3_ROWS = [
    ("A12", "Gudang", "`Meja Saya` → **Tugas gudang (terima, picking & kirim)** → [[Kerjakan]] → `Gudang & Logistik › Operasi Gudang › Barang Keluar`",
     "Buka tugas per gudang; cetak **Surat Pengambilan Barang** (picking list: alamat simpan, nomor roll, qty, SO).", "Tugas *Ambil di Gudang* bertanggal di masa depan masih **ditahan** → [[Rilis ke Antrean]] bila diambil lebih awal.",
     "Satu SO multi-gudang = beberapa tugas. Picking list belum mengurangi stok terjual.", "OK tugas lahir per gudang; hold pickup"),
    ("A13", "Gudang", "`Barang Keluar` → panel **Potong tertunda** → konfirmasi potong",
     "Untuk roll yang dicadangkan sebagian: ukur & potong fisik, isi panjang aktual & sisa/waste, cetak label roll anak, lalu **verifikasi label** (scan label roll anak).",
     "Label salah → ditolak. Roll induk sebelum dipotong tidak bisa di-pick.",
     "Roll anak lahir (mis. RL-36312-1) ter-reservasi untuk SO; sisa induk berkurang sesuai aktual.",
     "BUG F-05 alokasi SO tetap menunjuk roll induk"),
    ("A14", "Gudang", "`Barang Keluar` → [[Scan QR/RFID atau ketik nomor roll]]",
     "Scan tiap roll yang diambil; qty pick = panjang roll. Ulangi sampai semua roll baris terambil.",
     "Roll produk/gudang/pemilik berbeda atau bukan alokasi SO ini → ditolak dengan alasan.",
     "Status tugas *picking → packing*; SO *Sebagian dipick / Siap kirim*.", "OK roll asing ditolak; F-05 pick induk ditolak"),
    ("A15", "QC", "`Operasi Gudang › QC & Inspeksi` → SPK QC pesanan",
     "Jika SO meminta QC: Admin Gudang menugaskan SPK; QC [[Mulai diperiksa]], isi panjang inspect (yard) & cacat per interval 15 yd, [[Simpan hasil]]; keputusan lulus/tahan.",
     "QC sampling = sebagian roll (persen dari SO). Roll tidak lulus → ganti roll (Admin Sales **Ganti Roll**).",
     "Kirim tertahan dengan pesan *meminta QC… kirim menunggu SPK QC selesai* sampai lulus.", "OK kirim ditolak sebelum QC (SO-00043)"),
    ("A16", "Gudang", "`Barang Keluar` → [[Mulai Loading Check]]",
     "Scan seluruh roll yang naik kendaraan (handheld RFID). Sistem membandingkan dengan manifest SO.",
     "Roll kurang/lebih/salah SO → **blokir**. Roll tanpa tag → Admin Gudang memberi **pengecualian berizin** + alasan (A16b).",
     "Hasil check tersimpan; perubahan alokasi sesudah check membuat hasil basi → ulangi check.", "OK blokir tanpa RFID → override wh.admin"),
    ("A17", "Gudang", "`Barang Keluar` → [[Kirim]] (dispatch)",
     "Kirim qty yang sudah di-pick. Boleh sebagian bila kebijakan kirim sebagian aktif.",
     "Belum di-pick → ditolak. SO berbayar CBD/DP **seharusnya** menunggu pembayaran (lihat Alur I).",
     "**Surat Jalan KSC/SJ-xxxxx** terbit per keberangkatan; SO *Dikirim / Sebagian dikirim*; pendapatan & HPP dijurnal (gl_status posted).",
     "OK SJ-00005/00006; BUG F-10 CBD tetap terkirim"),
]


def a4():
    d = Diagram(["whadm", "drv", "cust", "sadm", "sys"], 8, lane_h={"whadm": 80, "drv": 80, "cust": 66, "sadm": 62, "sys": 58})
    d.n("sj", "sys", 0, "doc", "SJ belum diangkut")
    d.n("a18", "whadm", 1, "task", "Meja Gudang: Buat pengiriman", "A18")
    d.n("dm", "whadm", 2, "decision", "Cara kirim?")
    d.n("pk", "cust", 2, "task", "Tunjukkan kode pickup + identitas", "A22")
    d.n("a19", "drv", 3, "task", "Foto muat → Tandai Dimuat", "A19")
    d.n("a20", "drv", 4, "task", "Isi resi / plat & sopir → Berangkat", "A20")
    d.n("ds", "drv", 5, "decision", "Sampai?")
    d.n("fail", "whadm", 5, "task", "Gagal kirim: alasan → jadwalkan ulang", "A20b")
    d.n("a21", "drv", 6, "task", "Foto POD + nama penerima → Terkirim", "A21")
    d.n("rcv", "cust", 6, "task", "Terima & tanda tangan SJ")
    d.n("a23", "sadm", 7, "task", "Tandai diterima → SO Selesai", "A23")
    d.n("lI", "sys", 7, "link", "I")
    d.e("sj", "a18", fs_="t", ts="l")
    d.e("a18", "dm")
    d.e("dm", "a19", "ekspedisi / armada", fs_="b", ts="t", via=[(d.nodes["dm"]["cx"], d.nodes["a19"]["cy"] - 34), (d.nodes["a19"]["cx"], d.nodes["a19"]["cy"] - 34)])
    d.e("dm", "pk", "diambil pelanggan", fs_="l", ts="t", via=[(d.nodes["pk"]["cx"] - 52, d.nodes["dm"]["cy"]), (d.nodes["pk"]["cx"] - 52, d.nodes["pk"]["cy"] - 40), (d.nodes["pk"]["cx"], d.nodes["pk"]["cy"] - 40)])
    d.e("pk", "a23", "serah terima tervalidasi", fs_="b", ts="l", via=[(d.nodes["pk"]["cx"], d.nodes["a23"]["cy"])], color=G)
    d.e("a19", "a20")
    d.e("a20", "ds")
    d.e("ds", "fail", "gagal", fs_="t", ts="b", color=R)
    d.e("fail", "a19", fs_="l", ts="t", style="dash")
    d.e("ds", "a21", "ya")
    d.e("rcv", "a21", fs_="t", ts="b", style="dash")
    d.e("a21", "a23", fs_="r", ts="t", color=G)
    d.e("a23", "lI", fs_="b", ts="t")
    return d


A4_ROWS = [
    ("A18", "Admin Gudang", "`Meja Gudang` → **Surat Jalan belum diangkut logistik** → [[Buat pengiriman]] (`Gudang & Logistik › Pengiriman`)",
     "Pilih satu atau beberapa SJ (boleh beberapa SO dalam satu armada), mode **Ekspedisi** (kurir, layanan, ongkir) / **Armada sendiri** (kendaraan dari master, sopir) / **Diambil pelanggan**; ETA, tujuan, telepon penerima.",
     "Tanpa SJ → ditolak *Pilih minimal 1 Surat Jalan*.", "Nomor **KSC/LG-xxxxx**, status *Disiapkan*; manifest memuat semua SJ.", "OK LG-00001…00004 (2 SO satu armada)"),
    ("A19", "Sopir", "`Pengiriman` → detail → unggah **Foto muat** → [[Tandai Dimuat]]",
     "Sopir/petugas memotret barang naik kendaraan lalu menandai dimuat.", "Tanpa foto muat → ditolak *Wajib unggah FOTO MUAT*.",
     "Status *Dimuat*, waktu muat tercatat.", "OK penolakan & sukses"),
    ("A20", "Sopir", "`Pengiriman` → [[Berangkat]]",
     "Ekspedisi: isi **nomor resi**. Armada: plat & nama sopir wajib; kendaraan otomatis *dalam perjalanan*. Opsional: posisi/GPS di perjalanan.",
     "Ekspedisi tanpa resi → ditolak. Sopir sedang mengantar kiriman lain → ditolak.", "Status *Dalam perjalanan*.", "OK resi wajib"),
    ("A20b", "Admin Gudang", "`Pengiriman` → [[Tandai gagal kirim?]] → jadwalkan ulang",
     "Bila tidak sampai: isi alasan (≥3 huruf). Admin Gudang menjadwalkan ulang (kembali ke *Disiapkan*).", "Bongkar muatan dari *Dimuat* butuh alasan & izin manage.",
     "Status *Gagal kirim* dengan alasan; Sales menerima notifikasi.", "NA"),
    ("A21", "Sopir", "`Pengiriman` → unggah **Foto POD** → isi nama penerima → [[Tandai TERKIRIM?]]",
     "Di lokasi pelanggan: foto bukti terima, nama penerima, waktu terima.", "Tanpa POD / nama penerima → ditolak (pesan menyebut semua yang kurang).",
     "Status *Terkirim*; Sales diberi notifikasi. Admin Gudang menutup dengan [[Selesai]].", "OK POD wajib"),
    ("A22", "Admin Gudang", "`Pengiriman` (mode Diambil pelanggan) → [[Verifikasi & serahkan]]",
     "Pelanggan menunjukkan **kode pickup** (diberikan Sales) + nama & no. identitas pengambil.", "Kode salah → *KODE PICKUP SALAH — barang tidak boleh diserahkan*.",
     "Status *Diserahkan*; jejak pengambil tersimpan.", "OK kode salah ditolak (LG-00003)"),
    ("A23", "Admin Sales", "detail SO → [[Tandai diterima]] (izin `order.deliver`)",
     "Setelah pelanggan konfirmasi terima, tandai SO diterima. Gudang juga berwenang; **Sales tidak**.",
     "SO masih *Sebagian dikirim* → belum bisa (hanya status *Dikirim*).",
     "SO **Selesai (Delivered)**; roll keluar dari stok milik. Lanjut penagihan (**Alur I**).",
     "GAP F-06 POD logistik tidak otomatis menutup SO"),
]
