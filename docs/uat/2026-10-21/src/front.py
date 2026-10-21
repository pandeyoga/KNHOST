"""Bagian depan: sampul, daftar isi, cara membaca, peta besar, daftar keputusan."""
from html import escape
from diagram import Diagram, legend_svg, ROLE
from page import head, fmt, DOC_ID, VERSION, DATE

R, G = "#B91C1C", "#15803D"


def cover():
    lanes = ["sales", "sadm", "mgr", "md", "pur", "wh", "qc", "whadm", "fin"]
    strip = "".join(f'<div style="background:{ROLE[k][1]};opacity:.92">{escape(ROLE[k][0])}</div>' for k in lanes)
    return f"""<section class="cover"><div class="band"></div><div class="lanes">{strip}</div>
<div class="kicker" style="color:#93C5FD">Production IT · PT Kubus Teknologi Indonesia</div>
<h1>Panduan UAT End-to-End<br>ERP Kain Nusantara</h1>
<p class="sub">Satu rantai proses dari kebutuhan pelanggan sampai barang diterima dan pembayaran lunas — lengkap dengan
navigasi menu per langkah, gerbang persetujuan, harga khusus, percabangan, retur, pengadaan dan jadwal dua hari.</p>
<p class="sub" style="font-size:9.5pt;margin-top:5mm;max-width:150mm;color:#E2E8F0">
Alur: <b>A</b> Penjualan normal · <b>B</b> Persetujuan, harga khusus & kredit · <b>C</b> Stok kurang ·
<b>D</b> Pengadaan & penerimaan · <b>E</b> Sample · <b>F</b> Pesanan Khusus · <b>G</b> Logistik & transit ·
<b>H</b> Retur · <b>I</b> Penagihan & pembayaran · <b>J</b> Akses · <b>K</b> Konsistensi data</p>
<div class="meta">
<div><span class="lbl">Dokumen</span>{DOC_ID} · versi {VERSION}<br>Disusun {DATE}<br>Menggantikan KN-UAT-OPS-001 v1.0</div>
<div><span class="lbl">Kandidat acuan</span>Uji pra-UAT: main @ af24f9c (+ lokal)<br>Uji ulang: main @ a3f7936 + perubahan lokal sesi lain, 21 Okt 03.05<br>Data acuan lokal (restore demo)</div>
<div><span class="lbl">Pelaksanaan</span>2 hari · 08.00–17.00 WIB<br>Hari 1: Order-to-Cash<br>Hari 2: Hulu & hilir</div>
<div><span class="lbl">Status</span>Semua langkah <b>BELUM DIUJI</b> oleh peserta.<br>Uji pra-UAT tim IT: 17 temuan (7 prioritas 1).</div>
</div></section>"""


def toc(entries):
    rows = "".join(f'<div><span><b>{escape(code)}</b>{escape(title)}</span><span>{escape(str(pg))}</span></div>'
                   for code, title, pg in entries)
    return f'<section class="sec">{head("Daftar isi", "Isi dokumen", ["A4 lanskap", "Cetak berwarna disarankan"])}<div class="toc">{rows}</div></section>'


FLOWMAP = [
    ("A", "Penjualan normal (Order-to-Cash)", "Penjualan › POS · Meja Admin Sales · Operasi Gudang › Barang Keluar · Pengiriman", "Sales, Admin Sales, Manajer, Gudang, Admin Gudang, Sopir", "Hari 1 09.00–12.15", "A01–A23"),
    ("B", "Persetujuan, harga khusus & kredit", "Checkout › Minta Harga Khusus · Pusat Persetujuan · Meja Saya", "Sales, Admin Sales, Manajer, Finance", "Hari 1 13.15–14.15", "B01–B18"),
    ("C", "Stok kurang & rencana pemenuhan", "Meja Admin Sales › Perlu dipenuhi · Pesanan › Permintaan Internal", "Sales, Admin Sales, CST, Pembelian", "Hari 1 15.15–15.55", "C01–C09"),
    ("D", "Pengadaan & penerimaan barang", "Pembelian › Pengadaan / Pesanan Pembelian · Operasi Gudang › Barang Masuk · QC & Inspeksi", "Pembelian, Manajer, Admin Gudang, Gudang, MD Quality, QC, Finance", "Hari 2 10.15–11.30", "D01–D21"),
    ("E", "Sample", "POS › Order Sample · Pesanan Sample · Meja Sample", "Sales, Finance, Admin Sample, Gudang", "Hari 1 15.55–16.35", "E01–E08"),
    ("F", "Pesanan Khusus (OD)", "Penjualan › Pesanan Khusus · Desainer › Permintaan Desain · R&D › Permintaan Sample", "Sales, Manajer/PIC, Desainer, MD/R&D, Admin Sales, Pembelian", "Hari 2 08.30–10.00", "F01–F24"),
    ("G", "Logistik multi-gudang & transit", "Operasi Gudang › Stok, Transfer & Opname · Barang Keluar · Pengiriman", "Gudang, Admin Gudang, Sopir", "Hari 2 11.30–12.15", "G01–G08"),
    ("H", "Retur pelanggan", "Retur › Retur Pelanggan / Retur Antar-PT / Retur ke Supplier", "Sales, Manajer, Gudang, QC, MD Quality, Finance, CST", "Hari 2 13.15–14.45", "H01–H17"),
    ("I", "Penagihan & pembayaran", "Meja Finance · Pajak › Faktur Keluaran · Keuangan › Piutang / Rencana Bayar", "Finance, Admin Sales, Sales, Manajer", "Hari 1 14.15–15.00", "I01–I10"),
    ("J", "Akses per peran", "Login · Meja Saya · semua menu", "Semua peran + role kustom & view-only", "Hari 1 08.30 · Hari 2 15.00", "J01–J13"),
    ("K", "Konsistensi data & laporan", "Meja · daftar · detail · Pusat Export · laporan", "Semua peran", "Hari 2 15.00–15.45", "K01–K09"),
]


def flowmap_table():
    rows = "".join(f"<tr><td class='no'>{a}</td><td><b>{escape(b)}</b></td><td>{fmt('`' + c.replace(' · ', '` · `') + '`')}</td>"
                   f"<td>{escape(d)}</td><td>{escape(e)}</td><td>{escape(f)}</td></tr>" for a, b, c, d, e, f in FLOWMAP)
    return ("<h3>Peta alur dalam dokumen</h3><table class='grid compact'><colgroup><col style='width:4%'><col style='width:20%'>"
            "<col style='width:36%'><col style='width:22%'><col style='width:11%'><col style='width:7%'></colgroup>"
            "<thead><tr><th>Kode</th><th>Alur</th><th>Pintu menu utama</th><th>Peran utama</th><th>Sesi</th><th>Langkah</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>")


def reading():
    return f"""<section class="sec">{head("Cara membaca", "Cara memakai panduan ini", ["Untuk fasilitator, peserta & pencatat"])}
<div class="strip c3">
<div class="box"><b class="t">Struktur setiap halaman alur</b><ul>
<li><b>Diagram swimlane</b> di atas: satu lajur = satu peran; panah = serah terima; belah ketupat = keputusan; segi enam = gerbang ACC.</li>
<li><b>Kotak aturan</b>: keputusan di tahap itu, aturan sistem, bukti minimal, dan temuan pra-UAT terkait.</li>
<li><b>Tabel langkah</b> di bawah: nomor langkah sama dengan lencana pada diagram (mis. <b>A08</b>).</li></ul></div>
<div class="box"><b class="t">Kolom tabel langkah</b><ul>
<li><b>Navigasi</b>: <span class="nav">Menu › Tab</span> lalu tombol <span class="btn">Tombol</span> persis seperti di layar.</li>
<li><b>Aktivitas & input</b>: apa yang diketik/dipilih pengguna.</li>
<li><b>Keputusan / cabang</b>: pilihan yang mungkin dan ke langkah mana.</li>
<li><b>Hasil</b>: status, nomor dokumen, pesan sistem yang <u>harus</u> terlihat.</li></ul></div>
<div class="box a"><b class="t">Kolom "Uji pra-UAT" (dijalankan tim IT 21 Okt)</b><ul>
<li><span class="t-ok">✓</span> sudah dijalankan & sesuai (nomor dokumen bukti)</li>
<li><span class="t-bad">✗ F-xx</span> bug — langkah diperkirakan <b>Gagal</b> sampai diperbaiki</li>
<li><span class="t-warn">! F-xx</span> celah proses / perlu keputusan owner</li>
<li><span class="t-na">○</span> belum dijalankan — wajib diuji peserta</li></ul></div>
</div>
<h3>Simbol diagram</h3>{legend_svg()}
<div class="strip">
<div class="box g"><b class="t">Status hasil UAT</b><ul><li><b>Lulus</b>: semua hasil wajib terlihat + bukti.</li><li><b>Gagal</b>: perilaku berbeda dari aturan yang sudah jelas.</li><li><b>Terblokir</b>: prasyarat / keputusan / perangkat belum ada.</li><li><b>Tidak diuji</b>: belum dijalankan.</li></ul></div>
<div class="box"><b class="t">Aturan main</b><ul><li>Setiap peserta memakai <b>akun perannya sendiri</b> — jangan menjalankan alur dengan Admin.</li><li>Tiap langkah dicatat nomor dokumennya.</li><li>Jangan mengubah status lewat database untuk meneruskan uji.</li></ul></div>
<div class="box a"><b class="t">Bila ada hambatan</b><ul><li>Catat ≤ 5 menit di lembar temuan.</li><li>Pisahkan bug teknis dari keputusan bisnis.</li><li>Lanjut memakai data <b>tahap siap</b> yang disebut di jadwal, tulis titik mulainya.</li></ul></div>
<div class="box r"><b class="t">Yang diperbaiki dari v1.0</b><ul><li>Satu peta besar + diagram bercabang per alur.</li><li>Navigasi menu › tab › tombol di setiap langkah.</li><li>Gerbang ACC, harga khusus, kredit, CBD/DP.</li><li>Sampai barang diterima & <b>lunas</b>; retur sampai uang/pengganti.</li><li>Jadwal 2 hari dengan aktivitas & output per sesi; diuji ke aplikasi.</li></ul></div>
</div>{flowmap_table()}</section>"""


def big_map():
    lanes = ["cust", "sales", ("md", "MD · Desainer · R&D"), "sadm", "mgr", "pur", "wh", "qc", "whadm", "fin"]
    d = Diagram([l[0] if isinstance(l, tuple) else l for l in lanes], 11,
                lane_h={"cust": 46, "sales": 46, "md": 48, "sadm": 54, "mgr": 46, "pur": 44, "wh": 46, "qc": 44, "whadm": 46, "fin": 46})
    d.lanes = lanes
    def n(*a, h=None, **k):
        return d.n(*a, w=k.pop('w', 80), h=(h or 38), fs=7.8, **k)
    n("p0", "cust", 0, "task", "Kebutuhan pelanggan", h=34)
    n("p1", "sales", 1, "task", "POS → SO · Sample (A1, E)", "A1", h=36)
    n("p1b", "md", 1, "task", "Pesanan Khusus: desain · sampling · ACC (F)", "F", h=38)
    n("p2", "sadm", 2, "task", "Verifikasi kelengkapan (A2)", "A2", h=38)
    n("p3", "mgr", 3, "gate", "ACC harga · kredit · nilai (B)", "B", h=36)
    n("dc", "sadm", 4, "decision", "Stok cukup?", h=44)
    n("p4", "pur", 4, "task", "PR → PO / MKO (C, D1)", "C", h=36)
    n("p5", "wh", 5, "task", "Kedatangan · hitung fisik (D2)", "D", h=38)
    n("p6", "qc", 6, "task", "MDQ + QC → stok tersedia", h=36)
    n("p7", "sadm", 6, "task", "Konfirmasi → tugas gudang", h=38)
    n("p8", "wh", 7, "task", "Potong · pick · QC · muat (A3)", "A3", h=38)
    n("p9", "whadm", 8, "task", "SJ · kirim / transit / ambil (A4, G)", "G", h=38)
    n("p10", "cust", 9, "task", "Terima barang · POD", h=34)
    n("p11", "sadm", 9, "task", "Tandai diterima", h=36)
    n("p12", "fin", 10, "task", "Faktur pajak · kwitansi · LUNAS (I)", "I", h=38)
    n("p13", "cust", 10, "task", "Keluhan ≤ 21 hr → Retur (H)", "H", h=34)
    e = d.e
    e("p0", "p1", fs_="b", ts="l", via=[(d.nodes["p0"]["cx"], d.nodes["p1"]["cy"])])
    e("p0", "p1b", fs_="b", ts="l", via=[(d.nodes["p0"]["cx"] - 30, d.nodes["p0"]["cy"] + 17), (d.nodes["p0"]["cx"] - 30, d.nodes["p1b"]["cy"])], label="custom")
    e("p1b", "p1", "jadi SO", fs_="t", ts="b", style="dash", lx=d.nodes["p1"]["cx"] + 30, ly=(d.nodes["p1"]["cy"] + d.nodes["p1b"]["cy"]) / 2)
    e("p1", "p2", fs_="r", ts="t", via=[(d.nodes["p2"]["cx"], d.nodes["p1"]["cy"])])
    e("p2", "p3", fs_="b", ts="l", via=[(d.nodes["p2"]["cx"], d.nodes["p3"]["cy"])])
    e("p3", "dc", fs_="r", ts="b", via=[(d.nodes["dc"]["cx"], d.nodes["p3"]["cy"])])
    e("dc", "p4", "tidak", fs_="r", ts="t", via=[(d.nodes["dc"]["cx"] + 62, d.nodes["dc"]["cy"]), (d.nodes["dc"]["cx"] + 62, d.nodes["p4"]["cy"] - 30), (d.nodes["p4"]["cx"], d.nodes["p4"]["cy"] - 30)], color=R)
    e("p4", "p5", fs_="b", ts="l", via=[(d.nodes["p4"]["cx"], d.nodes["p5"]["cy"])])
    e("p5", "p6", fs_="b", ts="l", via=[(d.nodes["p5"]["cx"], d.nodes["p6"]["cy"])])
    e("p6", "p7", "dicadangkan", fs_="t", ts="b", color=G)
    e("dc", "p7", "ya", fs_="t", ts="t", via=[(d.nodes["dc"]["cx"], d.nodes["p7"]["cy"] - 30), (d.nodes["p7"]["cx"], d.nodes["p7"]["cy"] - 30)], color=G)
    e("p7", "p8", fs_="r", ts="t", via=[(d.nodes["p8"]["cx"], d.nodes["p7"]["cy"])])
    e("p8", "p9", fs_="b", ts="l", via=[(d.nodes["p8"]["cx"], d.nodes["p9"]["cy"])])
    e("p9", "p10", fs_="r", ts="b", via=[(d.nodes["p10"]["cx"], d.nodes["p9"]["cy"])])
    e("p10", "p11", fs_="b", ts="t", style="dash")
    e("p11", "p12", fs_="r", ts="t", via=[(d.nodes["p12"]["cx"], d.nodes["p11"]["cy"])])
    e("p10", "p13", "keluhan", color=R)
    return f"""<section class="sec">{head("Peta besar", "Satu rantai end-to-end: dari kebutuhan sampai lunas", ["11 alur · 40 titik keputusan", "Hari 1 = A B C E I · Hari 2 = D F G H J K"])}
<p class="lead">Semua pintu masuk bertemu di <b>SO</b>; SO tidak bergerak tanpa <b>verifikasi Admin Sales</b> dan <b>gerbang ACC</b>. Stok kurang diisi rantai
pengadaan yang hasilnya otomatis dicadangkan ke SO. Selesai saat barang <b>diterima pelanggan</b> dan <b>lunas</b>; keluhan ≤ 21 hari membuka retur.</p>
{d.render()}
<div class="strip">
<div class="box"><b class="t">Pintu masuk</b><ul><li>POS · Pesanan biasa → <b>A</b></li><li>POS · Order Sample → <b>E</b></li><li>Pesanan Khusus → <b>F</b> → SO</li><li>Retur pelanggan → <b>H</b></li></ul></div>
<div class="box a"><b class="t">Gerbang yang menahan</b><ul><li>Verifikasi Admin Sales (wajib)</li><li>ACC harga khusus / kredit / nilai / makloon</li><li>QC sebelum kirim (bila diminta)</li><li>Final Loading Check · bukti muat & POD</li></ul></div>
<div class="box g"><b class="t">Akhir yang dibuktikan</b><ul><li>SO <b>Selesai</b> (diterima pelanggan)</li><li>Faktur pajak terbit (PKP)</li><li>Kwitansi teralokasi → <b>Lunas</b></li><li>Retur: uang / pengganti / disposisi barang</li></ul></div>
<div class="box r"><b class="t">Titik rawan (temuan pra-UAT)</b><ul><li>F-09 SO terkunci setelah ACC ditolak</li><li>F-10 CBD/DP tidak menahan kirim</li><li>F-05 alokasi tidak ikut roll anak</li><li>F-11/F-12 retur: izin gudang/QC & QC tanpa terima</li></ul></div>
</div></section>"""


DECISIONS = [
    ("K01", "A03", "Jenis pesanan?", "Sales", "Biasa → A2 · Sample → E · Khusus → F", "Sample tidak boleh dicampur baris biasa"),
    ("K02", "A04", "Qty pas roll utuh?", "Sales + pelanggan", "Pas → lanjut · atas → qty naik · bawah → qty turun · potong → reservasi potong", "Tidak ada pembulatan diam-diam"),
    ("K03", "A05", "Harga nego / di bawah pricelist?", "Sales", "Tidak → harga sistem · ya → Minta Harga Khusus (B1)", "Diskon manual tidak tersedia"),
    ("K04", "A05", "Termin bayar?", "Sales", "Tunai · CBD · DP 50% · NET 7–90 · Bertahap 3x → I", "CBD/DP seharusnya menahan kirim (F-10)"),
    ("K05", "A05", "Minta QC sebelum kirim?", "Sales", "Tanpa QC · seluruh roll · sampling → A15", "Kirim tertahan sampai SPK QC lulus"),
    ("K06", "A06", "Kirim atau ambil?", "Sales + pelanggan", "Kirim (tgl opsional) · Ambil di Gudang (tgl wajib)", "Tugas gudang ditahan sampai tanggal ambil"),
    ("K07", "A07", "Stok entitas cukup?", "Sistem", "Ya → A2 · tidak + izin backorder → C · tidak tanpa izin → ditolak", "Stok global terlihat Sales; pemenuhan diatur Admin Sales"),
    ("K08", "B11", "Kredit over-limit / tunggakan?", "Sistem → Manajer", "Tidak → lanjut · ya → B14 setuju / tolak", "Override kredit sekali pakai"),
    ("K09", "A08", "Kelengkapan SO lengkap?", "Admin Sales", "Ya → ajukan · tidak → lengkapi (A08b)", "Konfirmasi sebelum verifikasi ditolak"),
    ("K10", "A10/B04", "Gerbang ACC: setuju?", "Manajer", "Setuju → SO Disetujui · tolak → B06 / B15", "Pengaju ≠ pemutus; Sales 403"),
    ("K11", "B07", "Alokasi berubah sesudah harga diajukan?", "Admin Sales", "Ya → ajukan ulang untuk versi alokasi baru", "Keputusan lama ditolak sistem"),
    ("K12", "C04", "Sumber pemenuhan kekurangan?", "Admin Sales", "Stok sendiri · PT lain (PIN → IC) · supplier (PR → PO) · tunggu", "Total rencana ≤ kekurangan; ulang tidak ganda"),
    ("K13", "D02/D07", "PR ≥ Rp50 jt / PO ≥ Rp100 jt?", "Sistem → Manajer", "Ya → ACC manajer · tidak → langsung", "Ambang di Aturan Persetujuan"),
    ("K14", "D04", "Jalur pengadaan?", "Pembelian", "Supplier → PO · makloon → Order Makloon", "Default dari master restock artikel"),
    ("K15", "D13", "Selisih kedatangan vs SJ/PO?", "Admin Gudang", "Terima dengan catatan · klaim supplier/mitra · tolak barang", "Stok = fisik, bukan qty pesanan"),
    ("K16", "D18", "Keputusan SPK inspeksi?", "Admin Gudang / Manajer", "Terima · sebagian · turun grade · tolak · tahan → lepas", "MD Quality ≠ QC 4-point"),
    ("K17", "D19", "Karantina kedatangan?", "QC", "Terima → tersedia · tolak → rusak / retur supplier (Nota Debit)", "Barang ditahan tidak bisa di-pick"),
    ("K18", "A13", "Ada reservasi potong?", "Gudang", "Ya → potong + label anak + verifikasi · tidak → pick", "Induk belum dipotong tidak bisa di-pick"),
    ("K19", "A16", "Muatan cocok manifest?", "Gudang / Admin Gudang", "Ya → kirim · tidak → perbaiki / pengecualian berizin", "Tanpa tag RFID butuh izin + alasan"),
    ("K20", "A18", "Cara kirim?", "Admin Gudang", "Ekspedisi (resi) · armada (plat + sopir) · diambil pelanggan (kode)", "Foto muat & POD wajib"),
    ("K21", "A20", "Sampai di pelanggan?", "Sopir", "Ya → POD → Terkirim · gagal → alasan → jadwal ulang", "Gagal kirim wajib alasan"),
    ("K22", "G04", "Tujuan pertama?", "Admin Gudang", "Langsung pelanggan → A4 · transit Jakarta → SJ baru Jakarta", "Penerimaan transit ≠ POD pelanggan"),
    ("K23", "E01", "Masih dalam batas sample?", "Sistem", "Ya → SOS · tidak → jual ecer (A)", "Woven ≤ 5 yd · knit ≤ 2 kg · hanger ≤ 0,5 yd"),
    ("K24", "E02/E03", "Sample berbayar?", "Finance / Admin Sample", "Gratis → teruskan · berbayar → Setujui Bayar dulu", "Teruskan sebelum disetujui ditolak"),
    ("K25", "F05", "OD disetujui?", "Manajer → Direksi", "Setuju → routing · tolak → selesai / revisi", "Rantai berjenjang dari matriks"),
    ("K26", "F06", "Jenis permintaan OD?", "Sistem", "Printing → desain (F2) · labdip/handfeel → R&D (F3)", "Spesifikasi diwarisi"),
    ("K27", "F11", "Keputusan PIC atas desain?", "PIC (satu cukup)", "ACC + nilai · minta revisi (alasan) · tahan → lepas", "Print paper bukan persetujuan"),
    ("K28", "F12", "Motif utama berubah?", "Sales", "Ya → pesanan redesign (OD baru) · tidak → revisi artwork sama", "OD lama tetap utuh"),
    ("K29", "F16", "Pemenang sample?", "R&D", "Pilih pemenang · ulang ronde", "Satu ACC tidak meluluskan jenis wajib lain"),
    ("K30", "F18", "Keputusan pelanggan atas sample?", "Admin Sales (dari pelanggan)", "ACC → F4 · revisi → reproofing · tolak → tutup", "Bukti WA/foto disimpan"),
    ("K31", "F19", "Harga final ≥ acuan?", "Admin Sales", "Ya → kunci harga · tidak → Special Price (B)", "Margin bawaan 30%"),
    ("K32", "F21", "Jalur pengadaan item OD?", "Pembelian", "Supplier (PR → PO) · makloon (PR → MKO)", "Ganti jalur saat aktif ditahan"),
    ("K33", "H03", "Klaim retur valid?", "Sistem", "Ya → izin manajer · tidak → tolak / pengecualian", "21 hari dari SJ s/d tanggal pengajuan"),
    ("K34", "H04", "Izinkan barang kembali?", "Manajer", "Setuju → perjalanan masuk · tolak → selesai", "Bukan keputusan kompensasi"),
    ("K35", "H10/H11", "Outcome retur?", "Finance (nilai) + Manajer", "Refund · saldo · nego/cutloss · tukar · tolak", "Hanya setelah QC (kecuali diskon foto)"),
    ("K36", "H12", "SO asal sudah lunas?", "Finance + pelanggan", "Belum → potong tagihan dulu · sudah → pilih refund / saldo", "KLR-10"),
    ("K37", "H14", "Tujuan barang retur?", "Sukacita", "Simpan · kembalikan ke CST", "CST wajib menerima"),
    ("K38", "H16", "Tindak lanjut CST?", "CST", "Simpan · retur supplier (≤ 21 hr) · buang BS", "Lewat masa supplier → simpan"),
    ("K39", "I02", "Bayar sebelum kirim?", "Finance", "CBD/DP → catat dulu, baru kirim · tidak → kirim lalu tagih", "Gerbang belum ada (F-10)"),
    ("K40", "I07", "Pembayaran vs tagihan?", "Finance", "Pas → lunas · kurang → sisa ditagih · lebih → deposit/refund/alokasi", "Di luar batas → manajer"),
]


def decisions():
    rows = "".join(f"<tr><td class='no'>{a}</td><td>{escape(b)}</td><td><b>{escape(c)}</b></td><td>{escape(d)}</td>"
                   f"<td>{fmt(e)}</td><td class='small'>{fmt(f)}</td></tr>" for a, b, c, d, e, f in DECISIONS)
    return f"""<section class="sec">{head("Percabangan", "Daftar 40 titik keputusan & ke mana tiap pilihan pergi", ["Dipakai fasilitator untuk memilih cabang uji"])}
<p class="lead">Setiap baris adalah belah ketupat pada diagram. Saat UAT, setiap pilihan minimal diuji sekali (positif) dan
pilihan yang seharusnya ditolak diuji sebagai uji negatif. Kolom <b>Di langkah</b> menunjuk nomor langkah di halaman alur.</p>
<table class="grid"><colgroup><col style="width:5%"><col style="width:7%"><col style="width:20%"><col style="width:13%"><col style="width:33%"><col style="width:22%"></colgroup>
<thead><tr><th>ID</th><th>Di langkah</th><th>Pertanyaan keputusan</th><th>Pemutus</th><th>Pilihan → tujuan</th><th>Aturan / batas sistem</th></tr></thead>
<tbody>{rows}</tbody></table></section>"""
