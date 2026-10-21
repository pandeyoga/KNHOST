"""Alur G — logistik multi-gudang & transit · Alur H — retur pelanggan · Alur I — penagihan & pembayaran."""
from diagram import Diagram

R, G = "#B91C1C", "#15803D"


def g1():
    d = Diagram(["wh", "whadm", "drv", "whj", "cust"], 9, lane_h={"wh": 78, "whadm": 82, "drv": 64, "whj": 80, "cust": 62})
    d.n("g01", "wh", 0, "task", "Pick per gudang (Woven · Knitting · Printing)", "G01")
    d.n("g02", "wh", 1, "task", "Serah terima ke Gudang Transit", "G02")
    d.n("g03", "whadm", 2, "task", "Final Loading Check seluruh muatan", "G03")
    d.n("g04", "whadm", 3, "task", "Satu pengiriman · beberapa SJ / SO (manifest)", "G04")
    d.n("dt", "whadm", 4, "decision", "Tujuan pertama?")
    d.n("lA4", "cust", 4, "link", "A4")
    d.n("g05", "drv", 5, "task", "Rancamalang → Jakarta", "G05")
    d.n("g06", "whj", 6, "task", "Terima di Jakarta: cocokkan roll", "G06")
    d.n("g07", "whj", 7, "task", "Cek muat ulang · SJ baru → pelanggan", "G07")
    d.n("g08", "cust", 8, "task", "POD pelanggan", "G08")
    d.e("g01", "g02")
    d.e("g02", "g03", fs_="r", ts="t", via=[(d.nodes["g03"]["cx"], d.nodes["g02"]["cy"])])
    d.e("g03", "g04")
    d.e("g04", "dt")
    d.e("dt", "lA4", "langsung pelanggan", fs_="b", ts="t")
    d.e("dt", "g05", "transit Jakarta", fs_="r", ts="t", via=[(d.nodes["g05"]["cx"], d.nodes["dt"]["cy"])])
    d.e("g05", "g06", fs_="r", ts="t", via=[(d.nodes["g06"]["cx"], d.nodes["g05"]["cy"])])
    d.e("g06", "g07")
    d.e("g07", "g08", fs_="r", ts="t", via=[(d.nodes["g08"]["cx"], d.nodes["g07"]["cy"])])
    return d


G_NOTE = "NA belum diuji — pastikan kandidat mendukung; bila belum, catat GAP (jangan diganti tombol status manual)"
G1_ROWS = [
    ("G01", "Gudang", "`Barang Keluar` (A12–A14) per gudang sumber",
     "Satu SO berisi woven + knitting + printing → tugas pick terpisah per gudang Rancamalang (Woven / Knitting / Printing).",
     "—", "Picking list per gudang; roll dari gudang lain tidak bisa dipindai ke tugas ini.", "OK tugas per gudang"),
    ("G02", "Gudang", "`Operasi Gudang › Stok, Transfer & Opname › Transfer`",
     "Transfer internal gudang sumber → **Rancamalang · Gudang Transit** (owner & reservasi tetap); gudang transit memindai serah terima per roll.",
     "Transfer terkait SO dengan owner berbeda → ditolak; harus transaksi antar-PT (C05).",
     "Lokasi fisik berpindah tercatat; belum serah terima pelanggan.", G_NOTE),
    ("G03", "Admin Gudang", "`Barang Keluar` → [[Mulai Loading Check]] (per SO / muatan)",
     "Scan semua roll yang naik kendaraan (handheld C72).", "Missing / extra / salah SO → blokir; tanpa tag → pengecualian berizin.", "Muatan tervalidasi.", "OK per SO"),
    ("G04", "Admin Gudang", "`Gudang & Logistik › Pengiriman` → [[Buat Pengiriman]] → pilih beberapa SJ",
     "Satu armada membawa beberapa SO; SJ tetap **per SO per keberangkatan**; manifest memuat semua SJ.", "—",
     "Nomor LG berisi beberapa SO.", "OK KSC/LG-00004 (2 SO)"),
    ("G05", "Sopir", "`Pengiriman` → Dimuat → Berangkat", "Perjalanan Rancamalang → Jakarta (bukan pengiriman pelanggan).", "—",
     "Barang *dalam perjalanan internal*; tidak dianggap diterima pelanggan.", G_NOTE),
    ("G06", ("Gudang · Jakarta", "warehouse@kainnusantara.id"), "`Barang Masuk` / transfer → terima di Jakarta",
     "Scan roll yang turun; bandingkan dengan yang benar-benar diberangkatkan; selisih per roll dicatat.", "Roll kurang/rusak → dicatat, tidak dipaksa penuh.",
     "Roll di transit Jakarta; reservasi SO tetap.", G_NOTE),
    ("G07", ("Gudang · Jakarta", "warehouse@kainnusantara.id"), "`Barang Keluar` → cek muat ulang → [[Kirim]]",
     "Validasi muatan lagi di Jakarta, terbitkan **SJ baru Jakarta → pelanggan** dengan referensi SO & SJ transit; manifest baru.", "Bukti scan Rancamalang tidak otomatis membuktikan muatan Jakarta.",
     "Rantai: SO → pick → transit → SJ transit → terima Jakarta → SJ pelanggan → POD.", G_NOTE),
    ("G08", "Sopir", "`Pengiriman` → POD (A21) → Admin Sales tandai diterima (A23)", "Penerimaan internal Jakarta **bukan** POD pelanggan.", "—", "SO Selesai.", ""),
]


def h1():
    d = Diagram(["cust", "sales", "mgr", "wh", "qc", "sys"], 9,
                lane_h={"cust": 64, "sales": 72, "mgr": 66, "wh": 80, "qc": 70, "sys": 66})
    d.lanes = ["cust", "sales", "mgr", ("wh", "Gudang Jakarta → Rancamalang"), "qc", "sys"]
    d.n("h01", "cust", 0, "task", "Keluhan (≤ 21 hari dari SJ)", "H01")
    d.n("h02", "sales", 1, "task", "Retur › Buat Retur: SO, roll terkirim, qty, sebab, foto", "H02")
    d.n("dv", "sys", 2, "decision", "Klaim valid?")
    d.n("exc", "sales", 2, "task", "Ditolak / Ajukan pengecualian", "H03b")
    d.n("h04", "mgr", 3, "gate", "Setujui pengajuan (izin kembali)", "H04")
    d.n("h05", "wh", 4, "task", "Jakarta: Terima di gudang (scan)", "H05")
    d.n("h06", "wh", 5, "task", "Kirim ke gudang lain → Transit QC", "H06")
    d.n("h07", "wh", 6, "task", "Rancamalang: Tiba di gudang tujuan", "H07")
    d.n("h08", "qc", 7, "task", "QC retur per roll (qty, cacat, grade)", "H08")
    d.n("lH2", "sys", 8, "link", "H2")
    d.e("h01", "h02", fs_="b", ts="l", via=[(d.nodes["h01"]["cx"], d.nodes["h02"]["cy"])])
    d.e("h02", "dv", fs_="b", ts="l", via=[(d.nodes["h02"]["cx"], d.nodes["dv"]["cy"])])
    d.e("dv", "exc", "tidak", fs_="t", ts="b", color=R)
    d.e("dv", "h04", "ya", fs_="r", ts="b", via=[(d.nodes["h04"]["cx"], d.nodes["dv"]["cy"])], color=G)
    d.e("h04", "h05", fs_="r", ts="t", via=[(d.nodes["h05"]["cx"], d.nodes["h04"]["cy"])])
    d.e("h05", "h06")
    d.e("h06", "h07")
    d.e("h07", "h08", fs_="r", ts="t", via=[(d.nodes["h08"]["cx"], d.nodes["h07"]["cy"])])
    d.e("h08", "lH2", fs_="r", ts="t", via=[(d.nodes["lH2"]["cx"], d.nodes["h08"]["cy"])])
    return d


H1_ROWS = [
    ("H01", "Pelanggan", "—", "Pelanggan mengeluh (warna beda, kotor/noda, sobek/lubang, salah kirim, kurang yard, handfeel). Masa klaim **21 hari dari SJ**.",
     "Barang Sisa bukan layanan retur; garansi = masa klaim 21 hari.", "—", "INFO"),
    ("H02", "Sales", "`Retur › Retur Pelanggan` → [[Buat Retur]] → pilih SO",
     "Daftar roll **yang benar-benar terkirim** (SJ, ID roll, qty, unit) tampil otomatis — tidak bisa tambah produk bebas. Pilih roll & qty klaim (boleh sebagian), kondisi, **sebab keluhan** (master), catatan; hangtag hilang / dipotong pelanggan; unggah foto (boleh menyusul sesuai kebijakan) → ajukan.",
     "Ganti SO A → B dengan cepat: daftar akhir harus SO B.", "Nomor **SRET-xxxxx** *Menunggu persetujuan*.", "OK SRET-00006"),
    ("H03", "Sistem", "otomatis",
     "Cek: roll milik SO ini, qty ≤ sisa terkirim dikurangi klaim aktif, tenggat **21 hari dari SJ sampai tanggal pengajuan** (diajukan hari ke-20, barang tiba hari ke-24 tetap sah — KLR-09), bukti wajib per tahap (bawaan: tidak wajib).",
     "Tidak valid → ditolak dengan alasan; di luar tenggat → [[Ajukan pengecualian]] (kebijakan/kewenangan).",
     "Tipe awal (retur/tukar/komplain) **belum** keputusan final kompensasi.", "OK qty > sisa ditolak; roll SO lain ditolak"),
    ("H04", "Manajer", "`Meja Saya` → **Retur menunggu ACC** → [[Putuskan]] (atau detail retur → [[Setujui]] / [[Tolak]])",
     "Setujui izin barang kembali untuk diperiksa.", "Sales → 403. Persetujuan ini **bukan** keputusan refund/tukar.", "Retur *Disetujui*.", "OK 403 Sales"),
    ("H05", ("Gudang · Jakarta", "warehouse@kainnusantara.id"), "detail retur → `Perjalanan Retur – satu timeline` → [[Terima di gudang]] → pilih gudang → scan → [[Catat scan]]",
     "Terima roll retur di **Jakarta**; dokumen terima (TRM) per scan.", "Roll bukan bagian retur ini → ditolak. Terima dua kali → ditolak.",
     "Posisi fisik per roll tercatat; belum jadi stok jual.", "BUG F-11 peran Gudang ditolak 403 (tidak punya izin retur) — diuji pakai Admin Sales"),
    ("H06", ("Gudang · Jakarta", "warehouse@kainnusantara.id"), "Perjalanan Retur → [[Kirim ke gudang lain (dalam perjalanan)]]",
     "Asal Jakarta, tujuan **Rancamalang · Gudang Transit** (area QC), kurir/armada.", "Tujuan wajib dipilih.",
     "Status *dalam perjalanan*; owner **tidak** berubah karena pindah lokasi.", "OK SRET-00006/SJ-1 (via Admin Sales)"),
    ("H07", ("Gudang · Rancamalang", "warehouse.rancamalang@kainnusantara.id"), "Perjalanan Retur → [[Tiba di gudang tujuan]] → scan",
     "Cocokkan roll dengan pengiriman sebelumnya.", "Roll kurang / salah tujuan → hambatan.", "Roll di area transit menunggu QC.", "OK TBA-1; BUG F-11"),
    ("H08", "QC", "detail retur → panel **Inspeksi** → mulai → isi hasil → [[Selesai Inspeksi]]",
     "Per roll: qty aktual hasil ukur, kondisi, cacat 4-point, grade, catatan. Potongan baik dari roll retur menjadi roll anak (ID merujuk induk).",
     "QC saat roll masih di perjalanan → ditolak.", "Retur *Selesai inspeksi*; hasil & bukti tampil di retur.",
     "BUG F-12 QC bisa mulai & selesai **tanpa scan terima** (SRET-00007); BUG F-11 QC 403"),
]


def h2():
    d = Diagram(["mdq", "fin", "mgr", "own", "ptl", "sup", "sadm"], 8,
                lane_h={"mdq": 64, "fin": 66, "mgr": 72, "own": 70, "ptl": 72, "sup": 56, "sadm": 60})
    d.lanes = [("mdq", "MD / MD Quality"), "fin", "mgr", "own", "ptl", "sup", "sadm"]
    d.n("h09", "mdq", 0, "task", "Cutloss: catat qty cacat (yard) & posisi", "H09")
    d.n("pc", "mdq", 2, "task", "Pecah roll: potongan baik dikirim lagi · cacat BS / dibuang", "H09b", w=150)
    d.n("h10", "fin", 1, "task", "Putuskan nilai kompensasi (harga × qty)", "H10")
    d.n("h11", "mgr", 2, "gate", "Selesaikan: refund · saldo · nego · tukar · tolak", "H11")
    d.n("dk", "mgr", 3, "decision", "Outcome?")
    d.n("h12", "fin", 4, "task", "Kurangi tagihan SO asal → sisa refund / saldo", "H12")
    d.n("dd", "own", 4, "decision", "Tujuan barang retur?")
    d.n("keep", "own", 5, "task", "Simpan stok Sukacita (grade & hold QC)", "H14")
    d.n("h15", "ptl", 5, "task", "CST wajib terima (Retur Antar-PT)", "H15")
    d.n("dc", "ptl", 6, "decision", "CST memutus?")
    d.n("ck", "ptl", 7, "task", "Simpan stok CST · atau buang BS + bukti", "H16")
    d.n("h17", "sup", 7, "task", "Retur ke Supplier (Nota Debit)", "H17")
    d.n("h13", "sadm", 4, "task", "Tukar: pesanan pengganti (yard aktual QC)", "H13")
    d.n("lA2", "sadm", 5, "link", "A2")
    d.e("h09", "h10", fs_="b", ts="l", via=[(d.nodes["h09"]["cx"], d.nodes["h10"]["cy"])])
    d.e("h09", "pc", "cutloss")
    d.e("h10", "h11", fs_="b", ts="l", via=[(d.nodes["h10"]["cx"], d.nodes["h11"]["cy"])])
    d.e("h11", "dk")
    d.e("dk", "h12", "refund / saldo / nego", fs_="t", ts="l", via=[(d.nodes["dk"]["cx"], d.nodes["h12"]["cy"])], lx=d.nodes["dk"]["cx"], ly=d.nodes["dk"]["cy"] - 40)
    d.e("dk", "dd", "barang kembali", fs_="r", ts="t", via=[(d.nodes["dd"]["cx"], d.nodes["dk"]["cy"])])
    d.e("dk", "h13", "tukar", fs_="b", ts="l", via=[(d.nodes["dk"]["cx"], d.nodes["h13"]["cy"])])
    d.e("h13", "lA2")
    d.e("dd", "keep", "simpan", color=G)
    d.e("dd", "h15", "ke CST", fs_="b", ts="l", via=[(d.nodes["dd"]["cx"], d.nodes["h15"]["cy"])])
    d.e("h15", "dc")
    d.e("dc", "ck", "simpan / BS")
    d.e("dc", "h17", "retur supplier", fs_="b", ts="l", via=[(d.nodes["dc"]["cx"], d.nodes["h17"]["cy"])])
    return d


H2_ROWS = [
    ("H09", "MD Quality", "detail retur → panel **Inspeksi / Cutloss** (izin *record_cutloss*, *split_cutloss*)",
     "Saat QC: catat **qty cacat dalam yard** (bukan kelipatan 15; produk kg dikonversi otomatis) + posisi cacat (dari–sampai) per roll.",
     "**Cutloss (KLR-01)**: pelanggan menerima potongan baik, kompensasi senilai qty cacat. Diskon tanpa barang kembali boleh dari foto/video (KLR-06).",
     "Pratinjau pecah roll; qty cacat tidak bisa diubah setelah Finance memutus.", "NA"),
    ("H09b", "MD Quality", "panel **Pecah roll cutloss**",
     "Roll dipecah fisik: potongan baik → dikirim kembali dengan **SJ baru merujuk SJ & SO asal**; potongan cacat → **BS** atau **dibuang** (dipilih per kasus oleh peran berwenang).", "—",
     "Roll anak berurutan dari induk; potongan BS tercatat sebagai stok BS (yard/kg), bukan roll.", "NA"),
    ("H10", "Finance", "detail retur → panel **Kompensasi** → isi nilai → **Catatan keputusan Finance (wajib)** → [[Selesaikan]]",
     "Nilai = **harga transaksi awal** (neto setelah diskon/harga khusus) × qty disetujui (KLR-02); diskon = **nominal rupiah per item** hanya untuk qty cacat (KLR-07). Checklist hangtag hilang / kain dipotong = **peringatan**, Finance memutus (KLR-08).",
     "—", "Kompensasi *diputus*; dasar hitung terlihat.", "NA"),
    ("H11", "Manajer", "detail retur → [[Selesaikan]] (izin *sales_return.approve*)",
     "Pilih outcome **Refund** · **Store credit (potong bon)** · **Nego (diskon/cutloss)** · **Tukar** · **Tolak**; boleh per item/qty; isi **bukti keputusan** (mis. *ACC Pak Budi via WA 21/10*) + lampiran; pilih gudang retur.",
     "Sebelum QC selesai → ditolak (kecuali diskon foto/video yang sudah diputus Finance). Admin Sales → 403.",
     "Retur *credit_settled / refund_settled / nego_settled / rejected*; keputusan, peran & bukti tersimpan.", "OK SRET-00006 saldo kredit; ditolak sebelum QC; 403 Admin Sales"),
    ("H12", "Finance", "`Keuangan › Saldo Kredit` · `Kas & Bank` · `Meja Finance`",
     "SO asal **belum lunas** → nilai mengurangi tagihan dulu, sisa → refund atau saldo. SO asal **sudah lunas** → pelanggan memilih refund atau saldo, **tidak wajib** memotong tagihan SO lain (KLR-10). Ongkir retur: penanggung dipilih per kasus (KN / pelanggan), langsung dijurnal (KLR-11, GL-01).",
     "—", "Satu posting idempoten; saldo pelanggan & piutang benar.", "NA"),
    ("H13", "Admin Sales", "detail retur → **Pesanan pengganti** → [[Buat pesanan pengganti]]",
     "SO pengganti tertaut retur: artikel/warna/grade **sama**; qty dalam **yard aktual hasil QC** (KLR-03); menunggu retur diterima & QC selesai; QC pengganti mengikuti request SO asal. Lanjut Alur A.",
     "Pengganti **lebih** (205 vs 195) → selisih dibayar pelanggan; **kurang** → refund/saldo; dinilai harga transaksi asal (KLR-04/05). Roll yang diretur & turunannya tidak boleh dikirim kembali ke pelanggan asal.",
     "Satu SO pengganti; ulang tidak membuat SO/delivery ganda.", "NA belum diuji"),
    ("H14", ("Admin Sales · pemilik Sukacita", "salesadmin@kainnusantara.id"), "detail retur → **Tujuan barang retur** → per roll [[Simpan sebagai stok]] / Kembalikan ke PT pemasok internal",
     "Sukacita memilih **simpan** (owner tetap, grade/hold mengikuti QC — bukan otomatis tersedia) atau **kembalikan ke CST**.",
     "Keputusan simpan tidak membalik pembelian internal.", "Opsi tampil; roll hasil QC (mis. RL-36311-1 48 yd grade B, karantina).", "OK opsi tampil; eksekusi belum diuji"),
    ("H15", "CST", "`Retur › Retur Antar-PT` → inbox CST → [[Terima]]",
     "CST **wajib menerima** retur internal; owner berpindah lewat dokumen; fisik tetap di gudang shared (tanpa gerakan fiktif).",
     "Tidak ada opsi menolak secara bisnis; selisih identitas/qty tetap dicatat.", "Dokumen pengembali ⇄ penerima tertaut.", "NA"),
    ("H16", "CST", "Retur Antar-PT → tindak lanjut", "CST memilih **simpan sebagai stok** atau **buang (BS) dengan bukti**, atau retur ke supplier (H17).",
     "Masa supplier lewat → simpan sesuai kondisi; tidak menggugurkan klaim pelanggan.", "Stok CST membawa grade/hold hasil QC.", "NA"),
    ("H17", ("Admin Gudang · CST", "wh.admin@kainnusantara.id"), "`Retur › Retur ke Supplier (Nota Debit)`",
     "Retur beli merujuk PO, penerimaan (GRN), roll & asal SO/SJ/retur pelanggan. Tenggat supplier **21 hari sampai klaim dikirim**, dihitung dari penerimaan aktual masing-masing (KLR-09).",
     "Dua penerimaan berbeda tanggal → tenggat masing-masing.", "Nota Debit; jejak SO → SJ → retur → QC → antar-PT → supplier utuh.", "NA"),
]


def i1():
    d = Diagram(["sales", "sadm", "fin", "mgr", "sys"], 9, lane_h={"sales": 66, "sadm": 64, "fin": 86, "mgr": 62, "sys": 80})
    d.n("i01", "sys", 0, "auto", "Termin dari SO: Tunai · CBD · DP · NET · Bertahap", "I01", w=104)
    d.n("dc", "sys", 1, "decision", "Bayar sebelum kirim?")
    d.n("i02", "fin", 1, "task", "Catat DP / CBD → uang muka", "I02")
    d.n("gk", "sys", 2, "gate", "Gerbang kirim (seharusnya)", "")
    d.n("lA3", "sys", 3, "link", "A3")
    d.n("i03", "fin", 3, "task", "Siap Faktur Pajak → Terbitkan", "I03")
    d.n("i04", "sadm", 4, "task", "Cetak Faktur Komersial & SJ", "I04")
    d.n("i05", "sales", 5, "task", "Follow-up jatuh tempo · lapor transfer", "I05")
    d.n("i06", "fin", 5, "task", "Catat kwitansi → alokasi FIFO / manual", "I06")
    d.n("dp", "sys", 6, "decision", "Bayar vs tagihan?")
    d.n("i07", "fin", 7, "task", "Putuskan selisih: deposit / refund / alokasi", "I07")
    d.n("i09", "mgr", 7, "gate", "Void · pembebasan denda · di luar wewenang", "I09")
    d.n("end", "sys", 8, "end", "SO LUNAS")
    d.e("i01", "dc")
    d.e("dc", "i02", "CBD / DP", fs_="t", ts="b", color=R)
    d.e("i02", "gk", fs_="r", ts="t", via=[(d.nodes["gk"]["cx"], d.nodes["i02"]["cy"])])
    d.e("dc", "gk", "tidak", color=G)
    d.e("gk", "lA3")
    d.e("lA3", "i03", "setelah kirim", fs_="t", ts="b")
    d.e("i03", "i04", fs_="t", ts="l", via=[(d.nodes["i03"]["cx"], d.nodes["i04"]["cy"])])
    d.e("i04", "i05", fs_="r", ts="b", via=[(d.nodes["i05"]["cx"], d.nodes["i04"]["cy"])])
    d.e("i05", "i06", fs_="r", ts="t", via=[(d.nodes["i05"]["cx"] + 60, d.nodes["i05"]["cy"]), (d.nodes["i05"]["cx"] + 60, d.nodes["i06"]["cy"] - 36), (d.nodes["i06"]["cx"], d.nodes["i06"]["cy"] - 36)], style="dash")
    d.e("i06", "dp", fs_="b", ts="l", via=[(d.nodes["i06"]["cx"], d.nodes["dp"]["cy"])])
    d.e("dp", "end", "pas", color=G)
    d.e("dp", "i07", "lebih", fs_="t", ts="l", via=[(d.nodes["dp"]["cx"], d.nodes["i07"]["cy"])])
    xk = d.nodes["i04"]["cx"] + d.col_w / 2 + 3
    d.e("dp", "i05", "kurang: sisa ditagih", fs_="b", ts="l", via=[(d.nodes["dp"]["cx"], d.height - 4), (xk, d.height - 4), (xk, d.nodes["i05"]["cy"])], color=R, lx=xk, ly=d.nodes["i05"]["cy"] + 34)
    d.e("i07", "end", fs_="b", ts="t", via=[(d.nodes["i07"]["cx"], d.nodes["end"]["cy"] - 30), (d.nodes["end"]["cx"], d.nodes["end"]["cy"] - 30)])
    d.e("i07", "i09", "di luar batas", fs_="b", ts="t", style="dash")
    return d


I1_ROWS = [
    ("I01", "Sales", "`Checkout › Termin & Lot` (A05) · `Keuangan › Rencana Bayar`",
     "Termin dipilih saat SO: **Tunai** · **CBD — Bayar Sebelum Kirim** · **DP 50% + Pelunasan** · **NET 7/14/30/60/90** · **Bertahap 3x**. Termin berlapis per badan usaha. Rencana Bayar untuk DP + cicilan / milestone.",
     "—", "Termin & jatuh tempo tercatat di SO.", "OK"),
    ("I02", "Finance", "`Meja Finance` → **Uang masuk** → [[Catat kwitansi]] · **Uang muka pesanan belum dikirim**",
     "CBD/DP: catat pembayaran sebelum barang keluar (uang muka; kewajiban sampai dikirim).",
     "**Harus**: gudang tidak bisa kirim sebelum syarat bayar terpenuhi.", "Uang muka tercatat; pendapatan diakui saat kirim.",
     "BUG F-10 tidak ada gerbang — SO CBD KSC/SO-00041 terkirim (SJ-00007) tanpa pembayaran"),
    ("I03", "Finance", "`Meja Finance` → **Siap terbitkan Faktur Pajak** → [[Terbitkan]] · `Akuntansi & Pajak › Pajak › Faktur Keluaran`",
     "PT PKP: isi kode transaksi (04), tanggal faktur; NSFP 16 digit menyusul dari Coretax ([[Cetak Faktur Pajak]]).",
     "Terbitkan ulang → ditolak (*gunakan Pengganti*). Non-PKP → tidak ada faktur pajak.", "**KSC/FKT-xxxxx**: DPP = 11/12 × dasar, PPN sesuai SO.",
     "OK FKT-00001 DPP 3.437.500 · PPN 412.500; ulang ditolak"),
    ("I04", "Admin Sales", "`Meja Admin Sales` → **Siap cetak Surat Jalan / Invoice** → [[Cetak]]",
     "Cetak **Faktur Komersial** (invoice) & SJ dari `Pusat Dokumen › Cetak PDF & Label`; kirim ke pelanggan.", "—", "Dokumen bernomor & bisa ditelusuri dari SO.", "INFO F-08 daftar invoice SO kosong; tagihan = Faktur Komersial PDF"),
    ("I05", "Admin Sales", "`Meja Admin Sales` → **Jatuh tempo & pengingat** → [[Follow-up]] · Sales: `Keuangan › Kasus Keuangan` (lapor)",
     "Ingatkan pelanggan sebelum/sesudah jatuh tempo. Sales yang menerima kabar *sudah transfer* melapor lewat Kasus Keuangan (tidak menutup kasus uang).", "—",
     "Daftar jatuh tempo sesuai termin.", "GAP F-16 jatuh tempo dihitung dari tanggal SO, SO belum dikirim ikut terdaftar"),
    ("I06", "Finance", "`Meja Finance` → **Uang masuk perlu dicatat & dialokasikan** → [[Catat kwitansi]]",
     "Isi **Jumlah Diterima**, **Metode** (Tunai → Kas Kecil; Transfer Bank/Giro/QRIS → Bank), tanggal, no. referensi; alokasi **Otomatis (FIFO)** atau **Manual per Pesanan** → [[Simpan Pembayaran]].",
     "Alokasi melebihi sisa SO → ditolak.", "Kwitansi **KSC/AR-xxxxx** (jurnal posted); SO *Sebagian* atau *Lunas*.", "OK AR-00003 (50%) → Sebagian; AR-00005 → Lunas"),
    ("I07", "Finance", "dialog selisih → [[Lanjutkan & simpan pembayaran]] · `Meja Finance › Selisih bayar perlu diputuskan` → [[Putuskan]]",
     "Lebih bayar: simpan deposit / refund / alokasi ke SO lain / write-off kecil (pembulatan). Kurang bayar: sisa tetap ditagih atau jadwal ulang.", "Di luar batas kewenangan → manajer.", "Keputusan & alasan tersimpan.", ""),
    ("I08", "Finance", "`Meja Finance` → **Denda perlu diterbitkan** → [[Terbitkan]] · `Keuangan › Piutang`",
     "Nota denda keterlambatan hasil hitungan sistem diterbitkan Finance; pembebasan denda → manajer. Pantau umur piutang.", "—", "Denda & piutang konsisten.", ""),
    ("I09", "Manajer", "kwitansi → void (alasan wajib) · keputusan di luar wewenang Finance",
     "Void membalik pembayaran di SO, kas & deposit; tercatat di audit.", "—", "Status bayar SO kembali sesuai.", ""),
    ("I10", "Sistem", "`Pesanan (SO) › detail › Perjalanan Pesanan`",
     "SO *Lunas*: piutang 0; Perjalanan Pesanan menampilkan *Dikirim · Diterima · Ditagih · Dibayar*.", "—", "Angka di SO, Meja Finance, Piutang & laporan sama.", "OK paid 4.162.500; F-07 langkah gudang salah"),
]
