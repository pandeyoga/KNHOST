"""Alur F — Pesanan Khusus (OD): intake → desain → sampling R&D → ACC pelanggan → harga → pengadaan → SO."""
from diagram import Diagram

R, G = "#B91C1C", "#15803D"
OD_NOTE = "NA modul OD berubah selama penyusunan (FE-01 lanjutan, a3f7936) — belum diuji pra-UAT"


def f1():
    d = Diagram(["cust", "sales", "mgr", "sys"], 9, lane_h={"cust": 66, "sales": 86, "mgr": 76, "sys": 80})
    d.n("f01", "cust", 0, "task", "Kebutuhan custom per produk (motif, warna, qty)", "F01")
    d.n("f02", "sales", 1, "task", "Pesanan Khusus › Buat: pelanggan, judul, target", "F02")
    d.n("f03", "sales", 2, "task", "Item A, B…: sumber, jenis uji, qty · unggah referensi", "F03")
    d.n("f04", "sales", 3, "task", "Simpan → Ajukan persetujuan", "F04")
    d.n("f05", "mgr", 4, "gate", "Rantai ACC: Manajer → Direksi (nilai besar)", "F05")
    d.n("dk", "mgr", 5, "decision", "Keputusan?")
    d.n("x", "sales", 5, "end", "Ditolak / revisi")
    d.n("f06", "sys", 6, "auto", "Routing otomatis per jenis permintaan", "F06")
    d.n("dt", "sys", 7, "decision", "Jenis?")
    d.n("lF2", "mgr", 7, "link", "F2")
    d.n("lF3", "sys", 8, "link", "F3")
    d.e("f01", "f02", fs_="b", ts="l", via=[(d.nodes["f01"]["cx"], d.nodes["f02"]["cy"])])
    d.e("f02", "f03")
    d.e("f03", "f04")
    d.e("f04", "f05", fs_="r", ts="t", via=[(d.nodes["f05"]["cx"], d.nodes["f04"]["cy"])])
    d.e("f05", "dk")
    d.e("dk", "x", "tolak", fs_="t", ts="b", color=R)
    d.e("dk", "f06", "setuju", fs_="b", ts="l", via=[(d.nodes["dk"]["cx"], d.nodes["f06"]["cy"])], color=G)
    d.e("f06", "dt")
    d.e("dt", "lF2", "printing", fs_="t", ts="b")
    d.e("dt", "lF3", "labdip / handfeel")
    return d


F1_ROWS = [
    ("F01", "Pelanggan", "—", "Kebutuhan produk yang belum ada: motif/artwork, warna (Pantone/labdip), handfeel, qty per produk (bisa >1 produk), target tanggal.",
     "Produk sudah ada di katalog → pesanan biasa (A).", "—", "INFO data acuan D-05: item A 100 yd + item B 200 yd"),
    ("F02", "Sales", "`Penjualan › Pesanan Khusus` → [[Buat Pesanan Khusus]]",
     "Isi pelanggan (pemilik permintaan), judul, kebutuhan umum, tanggal target, catatan pesanan.", "Pelanggan kosong → ditahan.",
     "Draf OD **SORD-yymmdd-xxxx**; berbeda dari HOLD pada SO normal.", OD_NOTE),
    ("F03", "Sales", "form OD → bagian Item → tambah item A, B…; unggah referensi",
     "Per item: **sumber** (induk produk existing untuk custom warna · desain existing yang belum jadi produk · desain dari pelanggan · desain baru), **jenis permintaan** (printing / labdip / handfeel / proofing), spesifikasi, qty + unit. Unggah file referensi pelanggan.",
     "Qty nol / sumber tidak sah → ditahan. Desain HOLD tidak boleh dipakai sebelum PIC melepas.",
     "Dua rincian A100 & B200 tersimpan terpisah; referensi terkait item.", OD_NOTE),
    ("F04", "Sales", "detail OD → [[Simpan pesanan khusus]] → **Ajukan**", "Ajukan OD draf ke persetujuan.", "Hanya OD draf yang bisa diajukan.",
     "Status *Menunggu persetujuan*; notifikasi ke penyetuju.", OD_NOTE),
    ("F05", "Manajer", "`Pusat Persetujuan` / detail OD → [[Setujui]] / [[Tolak pesanan]]",
     "Rantai persetujuan berjenjang dari matriks persetujuan (Manajer, lalu Direksi bila nilai besar).", "Akun tanpa wewenang → 403.",
     "Semua tingkat terpenuhi → OD *Disetujui*.", OD_NOTE),
    ("F06", "Sistem", "otomatis setelah disetujui",
     "Routing: **printing** → Permintaan Desain (DSR) ke Desainer (F2); **labdip/handfeel** → Permintaan Sample R&D dengan spesifikasi diwarisi (F3).",
     "Label *Special Order* / *redesign* dapat difilter di papan Desainer & R&D.", "Rantai dokumen OD ⇄ DSR ⇄ Sample ⇄ SKU ⇄ PR/PO ⇄ SO terbaca di panel rantai.", OD_NOTE),
]


def f2():
    d = Diagram(["md", "dsg", "mgr", "sales", "sys"], 8, lane_h={"md": 66, "dsg": 84, "mgr": 84, "sales": 62, "sys": 66})
    d.n("dsr", "sys", 0, "doc", "Permintaan Desain (DSR)")
    d.n("f07", "md", 1, "task", "Tugaskan desainer / desainer Ambil", "F07")
    d.n("f08", "dsg", 2, "task", "Kerjakan artwork · unggah versi ronde", "F08")
    d.n("f09", "dsg", 3, "task", "Centang Print paper → Ajukan untuk review", "F09")
    d.n("f10", "mgr", 4, "gate", "PIC review (satu PIC cukup)", "F10")
    d.n("dk", "mgr", 5, "decision", "Keputusan PIC?")
    d.n("hold", "mgr", 6, "task", "HOLD → Lepas penahanan oleh PIC")
    d.n("acc", "sys", 6, "auto", "Desain ACC + nilai → sample proofing lahir", "F11", w=128)
    d.n("red", "sales", 3, "task", "Motif utama berubah → pesanan redesign (OD baru)", "F12")
    d.n("lF3", "sys", 7, "link", "F3")
    d.e("dsr", "f07", fs_="t", ts="l", via=[(d.nodes["dsr"]["cx"], d.nodes["f07"]["cy"])])
    d.e("f07", "f08", fs_="r", ts="t", via=[(d.nodes["f08"]["cx"], d.nodes["f07"]["cy"])])
    d.e("f08", "f09")
    d.e("f09", "f10", fs_="r", ts="t", via=[(d.nodes["f10"]["cx"], d.nodes["f09"]["cy"])])
    d.e("f10", "dk")
    d.e("dk", "f08", "minta revisi (alasan)", fs_="t", ts="t", ym=d.nodes["f08"]["cy"] - 34 + 0, color=R,
        via=[(d.nodes["dk"]["cx"], d.nodes["f08"]["cy"] - 36), (d.nodes["f08"]["cx"], d.nodes["f08"]["cy"] - 36)])
    d.e("dk", "hold", "tahan", color=R)
    d.e("dk", "acc", "ACC + nilai", fs_="b", ts="l", via=[(d.nodes["dk"]["cx"], d.nodes["acc"]["cy"])], color=G)
    d.e("hold", "acc", "dilepas", fs_="b", ts="t", style="dash")
    d.e("acc", "lF3")
    return d


F2_ROWS = [
    ("F07", "MD", "`Desainer › Permintaan Desain` / `Meja MD › Permintaan desain` → [[Tugaskan]] · Desainer: `Meja Saya › Belum ditugaskan` → [[Ambil]]",
     "Pilih desainer & tenggat; sumber permintaan (Special Order / pelanggan / internal) terlihat.", "—", "DSR *Ditugaskan*; desainer menerima tugas.", OD_NOTE),
    ("F08", "Desainer", "`Meja Saya › Desain yang saya kerjakan` → [[Kerjakan]] · `Desain & Pattern`",
     "Kerjakan artwork; unggah versi ronde ini (versi lama tetap bisa dibuka).", "—", "Versi berkas & pelaku tercatat per ronde.", OD_NOTE),
    ("F09", "Desainer", "DSR → centang **Print paper** → [[Ajukan untuk review]] / [[Serahkan berkas final]]",
     "Print paper = checklist aktivitas cetak kertas per ronde (bukan persetujuan). Serah hasil harus menunjuk artwork nyata di galeri.", "—",
     "Status *Menunggu keputusan*; checklist punya ronde, waktu, pelaku.", OD_NOTE),
    ("F10", "PIC", "DSR / desain → [[Mulai review]]",
     "Salah satu PIC berwenang meninjau (tidak perlu semua PIC).", "Akun tanpa wewenang tidak bisa ACC / melepas HOLD.", "—", OD_NOTE),
    ("F11", "PIC", "[[Setujui (ACC) + nilai akhir]] · [[Minta revisi]] · [[Tahan desain]] → [[Lepas penahanan]]",
     "ACC dengan **nilai desain** (skor, bukan nilai penjualan). Revisi: **alasan wajib** → kembali ke desainer, ronde +1, checklist ronde lama tidak dianggap ronde baru. HOLD: desain tidak boleh dipakai proofing sampai dilepas.",
     "Revisi → F08. Tahan → tunggu PIC melepas. ACC → sample proofing lahir otomatis + notifikasi MD (F3).",
     "Siapa ACC & kapan tercatat; rapor desainer dihitung dari dokumen.", OD_NOTE),
    ("F12", "Sales", "detail OD → item → [[Buat pesanan redesign]] (*Ubah motif = pesanan khusus baru*)",
     "Perubahan motif utama **bukan** revisi artwork yang sama → OD baru berlabel *redesign* dengan tautan asal.", "—", "OD lama tetap utuh; OD baru terhubung.", OD_NOTE),
]


def f3():
    d = Diagram(["md", "sup", "sales", "cust", "sys"], 8, lane_h={"md": 86, "sup": 64, "sales": 72, "cust": 72, "sys": 62})
    d.n("smp", "sys", 0, "doc", "Permintaan Sample R&D", h=36)
    d.n("f13", "md", 1, "task", "Spesifikasi & supplier → Kirim Permintaan ke Supplier", "F13")
    d.n("f14", "sup", 2, "task", "Buat sample → kirim", "F14")
    d.n("f15", "md", 3, "task", "Catat Pengiriman / Setor hasil", "F15")
    d.n("f16", "md", 4, "task", "Nilai hasil → Pilih pemenang", "F16")
    d.n("f17", "sales", 5, "task", "Kirim sample ke pelanggan", "F17")
    d.n("dk", "cust", 6, "decision", "Keputusan pelanggan?")
    d.n("re", "md", 6, "task", "Reproofing: sample baru, artwork sama", "F18b")
    d.n("x", "sys", 6, "end", "Ditolak · OD ditutup")
    d.n("f18", "sales", 7, "task", "Catat ACC pelanggan + bukti", "F18")
    d.n("lF4", "sys", 7, "link", "F4")
    d.e("smp", "f13", fs_="t", ts="l", via=[(d.nodes["smp"]["cx"], d.nodes["f13"]["cy"])])
    d.e("f13", "f14", fs_="r", ts="t", via=[(d.nodes["f14"]["cx"], d.nodes["f13"]["cy"])])
    d.e("f14", "f15", fs_="r", ts="b", via=[(d.nodes["f15"]["cx"], d.nodes["f14"]["cy"])])
    d.e("f15", "f16")
    d.e("f16", "f17", fs_="r", ts="t", via=[(d.nodes["f17"]["cx"], d.nodes["f16"]["cy"])])
    d.e("f17", "dk", fs_="b", ts="l", via=[(d.nodes["f17"]["cx"], d.nodes["dk"]["cy"])])
    d.e("dk", "re", "minta revisi", fs_="t", ts="b", color=R)
    d.e("re", "f13", fs_="t", ts="t", via=[(d.nodes["re"]["cx"], 8), (d.nodes["f13"]["cx"], 8)], style="dash", color=R)
    d.e("dk", "f18", "ACC", fs_="r", ts="b", via=[(d.nodes["f18"]["cx"], d.nodes["dk"]["cy"])], color=G)
    d.e("dk", "x", "tolak", fs_="b", ts="t", color=R)
    d.e("f18", "lF4", fs_="r", ts="r", via=[(d.nodes["f18"]["cx"] + 54, d.nodes["f18"]["cy"]), (d.nodes["f18"]["cx"] + 54, d.nodes["lF4"]["cy"])])
    return d


F3_ROWS = [
    ("F13", "R&D", "`R&D › Permintaan Sample` → detail → [[Kirim Permintaan ke Supplier]]",
     "Periksa spesifikasi (diwarisi dari OD), pilih supplier/mitra peserta & pelaksana fisik sample, jenis uji yang **wajib untuk lini** (tidak semua bahan wajib tiga uji). Bahan sample diambil gudang ([[Ambil bahan]]).",
     "—", "Permintaan *Terkirim*; tenggat per supplier.", OD_NOTE),
    ("F14", "Supplier", "di luar sistem", "Supplier membuat sample labdip/handfeel/proofing dan mengirim.", "—", "—", OD_NOTE),
    ("F15", "R&D", "Permintaan Sample → [[Catat Pengiriman Sample]] / [[Setor hasil]]",
     "Catat kedatangan sample per supplier, siklus/ronde, jenis.", "—", "Status *Dikerjakan*.", OD_NOTE),
    ("F16", "R&D", "Permintaan Sample → [[Nilai]] → [[Pilih pemenang]] / [[Pilih supplier pemenang]] → [[Tandai Sample Jadi]]",
     "Nilai per jenis (skor, catatan penilai) → pilih pemenang & keputusan sampling. Satu ACC **tidak** meluluskan jenis wajib lain yang ditolak.",
     "Gagal / tidak ada pemenang → ulang ronde.", "Sample *Diputus*; OD fase *Sample siap*.", OD_NOTE),
    ("F17", "Sales", "detail OD → [[Kirim ke Pelanggan]]", "Kirim sample fisik ke pelanggan untuk diputus.", "—", "OD *Menunggu ACC pelanggan*; muncul di Meja Admin Sales.", OD_NOTE),
    ("F18", "Admin Sales", "`Meja Admin Sales` → **Pesanan khusus — menunggu ACC pelanggan** → [[Catat ACC]] (panel *Persetujuan Pelanggan*)",
     "Catat keputusan pelanggan: **ACC** / [[Minta revisi]] / [[Tolak]] + tanggal, catatan & bukti (foto/WA).",
     "Revisi → **reproofing** otomatis: sample R&D baru, spesifikasi diwarisi, **artwork sama**, OD kembali ke *Sampling* (F13). Tolak → OD ditutup.",
     "Ronde lama tetap tercatat; produksi belum dianggap ACC sebelum ACC pelanggan.", OD_NOTE),
]


def f4():
    d = Diagram(["sadm", "md", "pur", "wh", "sys"], 8, lane_h={"sadm": 80, "md": 66, "pur": 80, "wh": 62, "sys": 70})
    d.n("f19", "sadm", 0, "task", "Meja Admin Sales: Kunci harga (margin)", "F19")
    d.n("dp", "sys", 1, "decision", "Harga ≥ acuan?")
    d.n("lB", "sys", 2, "link", "B")
    d.n("f20", "md", 2, "task", "Buat SKU varian (tertaut induk, eksklusif)", "F20")
    d.n("f21", "pur", 3, "task", "Panel Pemenuhan: pilih jalur per item", "F21")
    d.n("dj", "pur", 4, "decision", "Jalur item?")
    d.n("lD", "pur", 5, "link", "D")
    d.n("f22", "wh", 5, "task", "Barang diterima & lulus MDQ/QC", "F22")
    d.n("f23", "sadm", 6, "task", "Ubah ke Pesanan Penjualan (SO)", "F23")
    d.n("so", "sys", 6, "doc", "SO tertaut OD")
    d.n("lA2", "sys", 7, "link", "A2")
    d.n("st", "sadm", 7, "auto", "Status OD ikut SO: Dikirim → Selesai", w=118)
    d.e("f19", "dp", fs_="b", ts="l", via=[(d.nodes["f19"]["cx"], d.nodes["dp"]["cy"])])
    d.e("dp", "lB", "tidak", color=R)
    d.e("dp", "f20", "ya", fs_="t", ts="l", via=[(d.nodes["dp"]["cx"], d.nodes["f20"]["cy"])], color=G)
    d.e("f20", "f21", fs_="r", ts="t", via=[(d.nodes["f21"]["cx"], d.nodes["f20"]["cy"])])
    d.e("f21", "dj")
    d.e("dj", "lD", "supplier / makloon", lx=(d.nodes["dj"]["cx"] + d.nodes["lD"]["cx"]) / 2, ly=d.nodes["dj"]["cy"] - 22)
    d.e("lD", "f22", fs_="b", ts="t")
    d.e("f22", "f23", fs_="r", ts="l", via=[(d.nodes["f22"]["cx"] + d.col_w / 2 + 2, d.nodes["f22"]["cy"]), (d.nodes["f22"]["cx"] + d.col_w / 2 + 2, d.nodes["f23"]["cy"])])
    d.e("f23", "so", fs_="b", ts="t")
    d.e("so", "lA2")
    d.e("lA2", "st", fs_="t", ts="b", style="dash")
    return d


F4_ROWS = [
    ("F19", "Admin Sales", "`Meja Admin Sales` → **Pesanan khusus — perlu kunci harga** → [[Kunci harga]]",
     "Harga final per item = harga kontrak supplier pemenang + **margin** (bawaan 30%, bisa diubah). Acuan awal: harga **Grade A** induk; tanpa induk → PIC Special Order.",
     "Di bawah acuan / nego → jalur **Special Price (B)**. Cost + margin saja tidak otomatis memenuhi keputusan harga Grade A.",
     "Harga terkunci per item (A & B), margin & cost tercatat; **PR/PO ke supplier pemenang lahir otomatis**.", OD_NOTE),
    ("F20", "MD", "detail OD → [[Buat SKU]]",
     "Custom warna dari induk → **varian/SKU baru** tertaut induk & item yang benar; warna lama tidak ditimpa. SKU **eksklusif** pelanggan pemilik OD.",
     "SKU OD dijual ke pelanggan lain → ditolak di POS.", "SKU aktif dengan tahap *produksi*.", OD_NOTE),
    ("F21", "Pembelian", "detail OD → panel **Pemenuhan** → [[Pilih jalur]] → [[Realisasi pengadaan]] / [[Buat & Ajukan PR]]",
     "Per item pilih **Supplier (PR → PO)** atau **Makloon (PR → MKO)** sesuai kemampuan produk/master; lanjut di Alur D.",
     "Ganti jalur saat dokumen aktif → ditahan / lewat pembatalan resmi. Realisasi ulang tidak menggandakan PO.",
     "PR/PO/MKO terkait item A/B; satu pengadaan aktif per realisasi.", OD_NOTE),
    ("F22", "Gudang", "Alur D2 (Kedatangan → hitung → MDQ/QC → tersedia)", "Penerimaan aktual menjadi acuan qty (bukan estimasi).", "—", "Stok item OD tersedia untuk SO.", OD_NOTE),
    ("F23", "Admin Sales", "detail OD → [[Ubah ke Pesanan Penjualan]]",
     "Konversi ke SO: item A & B, SKU, unit, harga **terkunci per item**; lanjut Alur A mulai verifikasi (A08).",
     "Item belum siap / harga belum terkunci → konversi ditahan. Ulang → tidak membuat SO kedua.",
     "SO tertaut OD (dua arah); total = Σ item.", OD_NOTE),
    ("F24", "Sistem", "otomatis", "SJ terbit untuk SO hasil OD → OD *Dikirim*; SO diterima → OD *Selesai*.", "—", "Status OD konsisten dengan SO.", OD_NOTE),
]
