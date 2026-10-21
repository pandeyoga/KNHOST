"""Alur D — pengadaan (supplier / makloon) & penerimaan + MD Quality/QC · Alur E — sample."""
from diagram import Diagram

R, G = "#B91C1C", "#15803D"


def d1():
    d = Diagram(["sadm", "pur", "mgr", "sup", "sys"], 9, lane_h={"sadm": 62, "pur": 96, "mgr": 66, "sup": 78, "sys": 66})
    d.n("d01", "sadm", 0, "task", "Kebutuhan: SO kurang · OD · Saran Reorder", "D01")
    d.n("pr", "sys", 1, "doc", "PR (Permintaan Pembelian)", "D02")
    d.n("dpr", "sys", 2, "decision", "PR ≥ Rp50 jt?")
    d.n("d03", "mgr", 2, "gate", "ACC PR", "D03")
    d.n("d04", "pur", 3, "task", "Sourcing per baris: beli / makloon", "D04")
    d.n("dj", "pur", 4, "decision", "Jalur?")
    d.n("d05", "pur", 5, "task", "Realisasi → PO supplier", "D05", dy=-22, h=36)
    d.n("d06", "pur", 5, "task", "Realisasi → Order Makloon", "D06", dy=24, h=36)
    d.n("dpo", "pur", 6, "decision", "PO ≥ Rp100 jt?", dy=-14, h=50)
    d.n("d07", "mgr", 6, "gate", "ACC PO", "D07")
    d.n("d08", "sup", 7, "task", "Supplier kirim barang + SJ", "D08")
    d.n("d08b", "sup", 5, "task", "Bahan keluar → mitra proses → hasil", "D08b")
    d.n("lD2", "sys", 8, "link", "D2")
    d.e("d01", "pr", fs_="b", ts="l", via=[(d.nodes["d01"]["cx"], d.nodes["pr"]["cy"])])
    d.e("pr", "dpr")
    d.e("dpr", "d03", "ya", fs_="t", ts="b")
    d.e("dpr", "d04", "tidak", fs_="r", ts="b", via=[(d.nodes["d04"]["cx"], d.nodes["dpr"]["cy"])], color=G)
    d.e("d03", "d04", fs_="r", ts="b", via=[(d.nodes["d04"]["cx"] - 20, d.nodes["d03"]["cy"])], color=G)
    d.e("d04", "dj")
    d.e("dj", "d05", "supplier", fs_="t", ts="l", via=[(d.nodes["dj"]["cx"], d.nodes["d05"]["cy"])])
    d.e("dj", "d06", "makloon", fs_="b", ts="l", via=[(d.nodes["dj"]["cx"], d.nodes["d06"]["cy"])])
    d.e("d05", "dpo", fs_="r", ts="l", via=[(d.nodes["dpo"]["cx"] - 70, d.nodes["d05"]["cy"]), (d.nodes["dpo"]["cx"] - 70, d.nodes["dpo"]["cy"])])
    d.e("dpo", "d07", "ya", fs_="b", ts="t")
    d.e("dpo", "d08", "tidak", fs_="r", ts="t", via=[(d.nodes["d08"]["cx"], d.nodes["dpo"]["cy"])], color=G)
    d.e("d07", "d08", "ACC", fs_="b", ts="l", via=[(d.nodes["d07"]["cx"], d.nodes["d08"]["cy"])], color=G)
    d.e("d06", "d08b", fs_="b", ts="t")
    d.e("d08", "lD2", fs_="r", ts="t", via=[(d.nodes["lD2"]["cx"], d.nodes["d08"]["cy"])])
    d.e("d08b", "lD2", "hasil makloon", fs_="b", ts="l", via=[(d.nodes["d08b"]["cx"], d.nodes["lD2"]["cy"])])
    return d


D1_ROWS = [
    ("D01", "Admin Sales", "otomatis dari C04 / F20 · manual `Pembelian › Pengadaan › Saran Reorder` / `Permintaan Pembelian`",
     "Kebutuhan pembelian lahir dari: kekurangan SO (rencana pemenuhan), Pesanan Khusus (jalur supplier/makloon per item), atau restock (Saran Reorder).",
     "—", "PR merujuk dokumen sumber (SO/OD) dua arah.", "OK PR-00042 dari SO-00045"),
    ("D02", "Sistem", "otomatis", "PR bernomor; baris membawa produk, qty, unit, gudang terima.",
     "Ambang PR (bawaan): ≥ Rp50 jt → manajer; di bawah → langsung disetujui.", "Status PR *Disetujui* / *Menunggu persetujuan*.", "OK disetujui otomatis"),
    ("D03", "Manajer", "`Pusat Persetujuan › Inbox Persetujuan` / `Meja Saya`", "ACC atau tolak PR di atas ambang.", "Tolak → kembali ke pengaju.", "Pemutus tercatat.", ""),
    ("D04", "Pembelian", "`Pembelian › Pengadaan › Permintaan Pembelian` → detail → **Sourcing**",
     "Per baris pilih jalur: **beli ke supplier** atau **makloon**. Default mengikuti master restock artikel (`Master Pembelian › Barang Supplier / Kontrak Mitra & Supplier`); penyimpangan beri alasan.",
     "MD hanya melihat (tidak bisa membuat PO).", "Ringkasan realisasi per baris (realized_qty, sisa).", "OK MD realisasi → 403"),
    ("D05", "Pembelian", "detail PR → [[Realisasi]] (→ PO)",
     "Pilih supplier, gudang penerimaan, tanggal kirim; boleh sebagian baris. Hasil: **PO KSC/PO-xxxxx** dan tugas inbound *menunggu barang*.",
     "Realisasi ulang tanpa sisa baris → ditolak. Supplier/kontrak/harga belum lengkap → tertahan dengan alasan.",
     "PO tertaut PR & SO/OD; qty belum diterima = *incoming* (bukan stok).", "OK PO-00028; ulang ditolak"),
    ("D06", "Pembelian", "detail PR → Wizard Makloon → `Pesanan Pembelian › Order Makloon`",
     "Jalur makloon: mitra, resep proses, output & unit, kebutuhan bahan/greige; **reservasi bahan ≠ pengeluaran**. Cetak SPK Makloon.",
     "Stok bahan kurang / salah jenis atau tahap / mitra tidak sah → ditahan.", "MKO tertaut PR; komitmen bahan terlihat.", "NA belum diuji"),
    ("D07", "Manajer", "`Pusat Persetujuan` → **Pesanan pembelian menunggu ACC**", "PO ≥ Rp100 jt (bawaan) wajib ACC.", "—",
     "Riwayat di `Pusat Persetujuan › Riwayat Persetujuan PO`.", ""),
    ("D08", "Supplier", "di luar sistem → SJ supplier", "Supplier mengirim barang + Surat Jalan supplier (nomor PO tercantum).",
     "—", "Gudang menerima di Alur D2.", ""),
    ("D08b", "Gudang", "`Order Makloon` → pengeluaran bahan",
     "Makloon: gudang mengeluarkan bahan sesuai dokumen (stock movement keluar tepat sekali), mitra memproses; hasil kembali lewat Kedatangan (mitra makloon).",
     "Hasil aktual boleh ≠ estimasi (mis. 192 dari rencana 200 yd) — tidak dipaksa sama.", "Sisa bahan, susut & klaim mitra tetap terlihat (`Rekap Susut & Klaim Mitra`).", "NA belum diuji"),
]


def d2():
    d = Diagram(["whadm", "wh", "mdq", "qc", "sys"], 9, lane_h={"whadm": 80, "wh": 68, "mdq": 66, "qc": 74, "sys": 70})
    d.n("d10", "whadm", 0, "task", "Barang Masuk: Buat kedatangan", "D10")
    d.n("d11", "whadm", 1, "task", "Foto SJ / entri manual · kepala SJ & baris", "D11")
    d.n("d12", "wh", 2, "task", "Hitung fisik per roll (panjang / berat, LOT)", "D12")
    d.n("ds", "sys", 3, "decision", "Selisih vs SJ / PO?")
    d.n("d13", "whadm", 3, "task", "Rekonsiliasi: terima dg catatan / klaim / tolak", "D13")
    d.n("d14", "whadm", 4, "task", "Tutup Penerimaan", "D14")
    d.n("ins", "sys", 5, "auto", "Roll karantina · SPK inspeksi lahir")
    d.n("d15", "whadm", 5, "task", "Tugaskan petugas SPK", "D15")
    d.n("d16", "mdq", 6, "task", "Warna/labdip & handfeel vs sample ACC", "D16")
    d.n("d17", "qc", 6, "task", "QC 4-point per 15 yd", "D17")
    d.n("dk", "whadm", 7, "decision", "Keputusan SPK?", "D18")
    d.n("d19", "qc", 8, "task", "Antrean karantina: keputusan QC", "D19")
    d.n("d20", "sys", 8, "doc", "Stok tersedia · SO dicadangkan")
    d.e("d10", "d11")
    d.e("d11", "d12", fs_="b", ts="l", via=[(d.nodes["d11"]["cx"], d.nodes["d12"]["cy"])])
    d.e("d12", "ds", fs_="b", ts="l", via=[(d.nodes["d12"]["cx"], d.nodes["ds"]["cy"])])
    d.e("ds", "d13", "ya", fs_="t", ts="b", color=R)
    d.e("ds", "d14", "tidak", fs_="r", ts="b", via=[(d.nodes["d14"]["cx"], d.nodes["ds"]["cy"])], color=G)
    d.e("d13", "d14")
    d.e("d14", "ins", fs_="r", ts="l", via=[(d.nodes["d14"]["cx"] + d.col_w / 2 + 2, d.nodes["d14"]["cy"]), (d.nodes["d14"]["cx"] + d.col_w / 2 + 2, d.nodes["ins"]["cy"])])
    d.e("ins", "d15", fs_="t", ts="b")
    d.e("d15", "d16", fs_="r", ts="t", via=[(d.nodes["d16"]["cx"], d.nodes["d15"]["cy"])])
    d.e("d16", "d17", fs_="b", ts="t")
    d.e("d17", "dk", fs_="r", ts="b", via=[(d.nodes["dk"]["cx"], d.nodes["d17"]["cy"])])
    d.e("dk", "d19", "terima / turun grade", fs_="r", ts="t", via=[(d.nodes["d19"]["cx"], d.nodes["dk"]["cy"])], color=G)
    d.e("d19", "d20", fs_="b", ts="t", color=G)
    return d


D2_ROWS = [
    ("D10", "Admin Gudang", "`Gudang & Logistik › Operasi Gudang › Barang Masuk` → [[Buat kedatangan]]",
     "Pilih mitra (supplier / makloon), gudang penerimaan, PO/MKO yang datang. Satu kedatangan = satu SJ satu mitra.",
     "Gudang biasa boleh membuat & entri manual, tetapi isi kepala SJ & baris butuh izin *review* (Admin Gudang).",
     "Nomor **KSC/GRN-xxxxx** status *Draf*.", "OK GRN-00001"),
    ("D11", "Admin Gudang", "kedatangan → unggah foto SJ (baca otomatis) atau entri manual",
     "Koreksi hasil baca: nomor & tanggal SJ, nama pemasok tercetak, referensi PO; baris barang (qty & unit menurut SJ, jumlah roll) → pilih **target PO**.",
     "Mulai hitung ditolak bila nomor SJ / baris kosong.", "Status *Review → Hitung*.", "OK NOT_READY ditolak"),
    ("D12", "Gudang", "kedatangan → [[Hitung fisik]] → scan label supplier / [[Cetak label KN roll ini]]",
     "Per roll catat **fisik**: panjang (yard/meter) atau berat (kg), LOT supplier, grade; tempel label. Penerimaan **bruto dari fisik sebelum dipotong**.",
     "Roll tanpa label → catat manual (override) dengan alasan.", "Roll lahir status *receiving* (belum stok jual).", "OK 2 roll 19,6 + 18,9 kg"),
    ("D13", "Admin Gudang", "kedatangan → [[Rekonsiliasi]]",
     "Sistem menampilkan selisih: kurang vs SJ (toleransi), jumlah roll beda, barang tidak di SJ, melebihi sisa PO. Putuskan per selisih: [[Terima dengan catatan]] / klaim supplier/mitra / [[Tolak barang]] + alasan.",
     "Selisih blokir wajib diputus sebelum tutup.", "Contoh uji: dihitung 38,5 kg vs SJ 40 kg (toleransi ±0,8) → wajib diputus.", "OK"),
    ("D14", "Admin Gudang", "kedatangan → [[Tutup Penerimaan]]",
     "Posting penerimaan: stok bertambah sebesar **fisik**; PO menjadi *Sebagian diterima* bila kurang; sisa PO tetap *incoming*.",
     "Klik ganda tidak memposting dua kali.", "Roll status **karantina**; SPK inspeksi (INS) otomatis untuk penerimaan PO.", "OK stok 38,5 kg (bukan 40)"),
    ("D15", "Admin Gudang", "`Meja Gudang` → **SPK inspeksi belum ditugaskan** → [[Tugaskan]]",
     "Pilih petugas (QC), bagian, tanggal SPK.", "SPK tanpa petugas tidak bisa dimulai.", "SPK *Ditugaskan*.", "OK"),
    ("D16", "MD Quality", "`Operasi Gudang › QC & Inspeksi` → Dokumen Inspeksi (INS) → baris roll → **MD Quality**",
     "Pilih roll yang diuji (sebagian/semua). Bandingkan dengan **sample ACC**: hasil warna (sesuai / beda shade / tolak), handfeel (sesuai / beda / tolak, skor 1–5); potongan uji (0,25 yd) dicatat sebagai pemakaian.",
     "Tanpa sample acuan → hanya pengamatan (Meja MD: *SPK tanpa acuan sample*).", "Dua indikator terpisah; sisa roll berkurang sesuai potongan.", "INFO MDQ bisa isi saat SPK masih draf (F-13)"),
    ("D17", "QC", "SPK → [[Mulai diperiksa]] → **QC 4-point** → [[Simpan hasil]]",
     "Isi panjang diinspeksi (selalu **yard**, walau stok kg) & cacat per interval 15 yd; grade saran dari total poin.", "Interval di luar panjang tidak boleh diisi.", "Hasil per roll tersimpan.", "OK"),
    ("D18", "Admin Gudang", "SPK → [[Keputusan]] (izin *inspection.decide*)",
     "Putuskan: terima / terima sebagian / turun grade / tolak → tutup SPK. Barang ditahan → [[Lepas tahanan barang]] oleh MD Quality/manajer + alasan, atau [[Tolak barang yang ditahan]].",
     "QC & MD Quality tidak punya izin memutus SPK (bawaan).", "SPK *Selesai*.", "OK INS-00019"),
    ("D19", "QC", "`QC & Inspeksi` → antrean **karantina kedatangan** → keputusan",
     "Terima qty (grade) dan/atau tolak qty (disposisi: rusak / **retur ke supplier → Nota Debit otomatis**).", "—",
     "Roll **tersedia**; tugas inbound selesai.", "GAP F-14 roll tetap karantina sesudah SPK 'terima' — perlu keputusan kedua"),
    ("D20", "Sistem", "otomatis + `Stok, Transfer & Opname` / `Lokasi Rak` (putaway)",
     "Stok tersedia dialokasikan FIFO ke SO backorder (C08); putaway ke rak/bin.", "—", "SO backorder berkurang; saldo per gudang/bin benar.", "OK 38,5 kg dicadangkan ke SO-00045"),
    ("D21", "Finance", "`Pembelian › Hutang Pemasok` → Tagihan Supplier → Kontrabon → `Meja Finance › Hutang supplier jatuh tempo` → [[Bayar]]",
     "Tagihan supplier dicocokkan dengan penerimaan (GR belum ditagih), tukar faktur (kontrabon), bayar sesuai termin.", "Pembayaran sebelum persetujuan kontrabon diblokir (bila diaktifkan).",
     "Hutang PO lunas.", "NA di luar uji pra-UAT"),
]


def e1():
    d = Diagram(["sales", "fin", "smp", "wh", "sys"], 8, lane_h={"sales": 72, "fin": 66, "smp": 70, "wh": 70, "sys": 74})
    d.n("e01", "sales", 0, "task", "POS › Order Sample: jenis & gratis/berbayar", "E01")
    d.n("db", "sys", 1, "decision", "Dalam batas sample?")
    d.n("lA", "sales", 1, "link", "A")
    d.n("sos", "sys", 2, "doc", "SOS · Pesanan Sample", "E02")
    d.n("dp", "sys", 3, "decision", "Berbayar?")
    d.n("e03", "fin", 3, "gate", "Setujui Bayar", "E03")
    d.n("e04", "smp", 4, "task", "Meja Sample: Teruskan ke Gudang", "E04")
    d.n("e05", "wh", 5, "task", "Potong: scan roll induk, panjang aktual", "E05")
    d.n("e06", "smp", 6, "task", "Admin Cutting terima hasil potong", "E06")
    d.n("e07", "wh", 7, "task", "Kirim → SJ · pengiriman / ambil", "E07")
    d.n("e08", "fin", 7, "task", "Catat pembayaran (berbayar)", "E08")
    d.e("e01", "db", fs_="b", ts="l", via=[(d.nodes["e01"]["cx"], d.nodes["db"]["cy"])])
    d.e("db", "lA", "tidak: jual ecer", fs_="t", ts="b", color=R)
    d.e("db", "sos", "ya")
    d.e("sos", "dp")
    d.e("dp", "e03", "ya", fs_="t", ts="b")
    d.e("dp", "e04", "gratis", fs_="r", ts="b", via=[(d.nodes["e04"]["cx"], d.nodes["dp"]["cy"])], color=G)
    d.e("e03", "e04", fs_="r", ts="t", via=[(d.nodes["e04"]["cx"], d.nodes["e03"]["cy"])], color=G)
    d.e("e04", "e05", fs_="b", ts="l", via=[(d.nodes["e04"]["cx"] + 20, d.nodes["e04"]["cy"] + 32), (d.nodes["e05"]["cx"] - 70, d.nodes["e04"]["cy"] + 32), (d.nodes["e05"]["cx"] - 70, d.nodes["e05"]["cy"])])
    d.e("e05", "e06", fs_="t", ts="b", via=[(d.nodes["e05"]["cx"], d.nodes["e06"]["cy"] + 40), (d.nodes["e06"]["cx"], d.nodes["e06"]["cy"] + 40)])
    d.e("e06", "e07", fs_="r", ts="t", via=[(d.nodes["e07"]["cx"], d.nodes["e06"]["cy"])])
    d.e("e07", "e08", "berbayar", fs_="t", ts="b", style="dash", via=[(d.nodes["e07"]["cx"] + 30, d.nodes["e07"]["cy"] - 35), (d.nodes["e08"]["cx"] + 30, d.nodes["e08"]["cy"] + 33)])
    return d


E1_ROWS = [
    ("E01", "Sales", "`Penjualan › POS` → [[Kosongkan untuk ganti jenis]] → **Order Sample** → item [[Jual sebagai sample (permintaan potong ke gudang)]]",
     "Pilih jenis: **Standar** (woven ≤ 5 yd, knit ≤ 2 kg) · **Hanger** (woven ≤ 0,5 yd) · **Catalogue** (1 yd tiap warna yang tersedia + 2 yd satu warna *soft*, disusun server dari template). Pilih **Gratis** atau **Berbayar** (wajib) dan lokasi potong.",
     "Melebihi batas → ditolak (*lebih dari itu jual sebagai ECER berbayar* → Alur A). Benang tidak bisa jadi sample. Sample dicampur roll biasa → ditolak.",
     "Batas berlaku di server, bukan hanya layar.", "OK 6 yd ditolak; tanpa gratis/berbayar ditolak; campur ditolak"),
    ("E02", "Sistem", "otomatis", "Nomor **KSC/SOS-xxxxx** terpisah dari SO; muncul di `Penjualan › Pesanan Sample` & `Meja Sample`.",
     "Gratis → *Siap diteruskan ke gudang*. Berbayar → *menunggu persetujuan pembayaran*. Barang milik PT lain → permintaan internal, bukan memotong stok PT lain.",
     "Harga berbayar dari master harga sample per induk.", "OK SOS-00002 Rp83.250"),
    ("E03", "Finance", "`Penjualan › Pesanan Sample` / `Meja Sample` → **Sample berbayar — menunggu persetujuan pembayaran** → [[Setujui Bayar]]",
     "Pastikan pembayaran/kesepakatan bayar sudah ada, isi catatan, setujui. Admin Sample juga berwenang.", "Sales → 403. Teruskan sebelum disetujui → 409.",
     "SOS *Disetujui*.", "OK"),
    ("E04", "Admin Sample", "`Meja Sample` → **Siap diteruskan ke gudang** → [[Teruskan ke Gudang]]",
     "Teruskan ke gudang; untuk catalogue boleh mengganti warna *soft* (hanya komponen tambahan, berjejak).", "—",
     "Tugas potong sample (*sample_cut*) lahir di gudang.", "OK 1 tugas"),
    ("E05", "Gudang", "`Meja Saya` → **Sample untuk dipotong** → [[Potong]]",
     "Scan roll induk (RFID/QR/nomor), potong, catat **panjang aktual**.", "Roll produk lain → ditolak *ROLL_WRONG_PRODUCT*. Lokasi tanpa kemampuan cutting → ditolak.",
     "Roll anak (mis. RL-36312-2) tertaut induk; induk berkurang sesuai aktual; nilai SOS mengikuti panjang aktual.", "OK 3,1 yd; induk 88,99 → 85,89"),
    ("E06", "Admin Sample", "`Meja Sample` / meja cutting → terima hasil potong",
     "Admin Cutting menerima potongan dari gudang (serah terima).", "Kirim sebelum diterima → ditolak *belum diterima Admin Cutting*.", "Jejak serah terima tersimpan.", "OK"),
    ("E07", "Gudang", "`Barang Keluar` → [[Kirim]] → pengiriman seperti A18–A23",
     "SJ sample terbit; kirim (ekspedisi/armada) atau ambil.", "Selesai potong **belum** berarti terkirim ke pelanggan.", "SOS *Dikirim* → *Selesai*.", "OK SJ-00009"),
    ("E08", "Finance", "`Meja Finance` → [[Catat kwitansi]] (Alur I)",
     "Untuk sample berbayar catat uang masuk atas nilai **aktual**.", "—", "SOS lunas.",
     "GAP F-15 nilai naik 83.250 → 86.025 setelah potong aktual, sesudah *Setujui Bayar*; status bayar tetap pending"),
]
