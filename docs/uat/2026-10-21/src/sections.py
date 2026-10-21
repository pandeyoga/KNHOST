"""Urutan cetak dokumen + kotak aturan per halaman alur."""
import json
import os
from page import head, steps_table, boxes, fmt
import flows_a as A
import flows_bc as BC
import flows_de as DE
import flows_f as F
import flows_ghi as GHI
import front
import sched
import back

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES_JSON = os.path.join(HERE, "toc_pages.json")


def flow_page(kicker, title, diagram, rows, chips=(), lead="", info=None, info_cols=4):
    parts = ['<section class="sec">', head(kicker, title, chips)]
    if lead:
        parts.append(f'<p class="lead">{fmt(lead)}</p>')
    parts.append(diagram.render())
    if info:
        parts.append(boxes(info, info_cols))
    parts.append(steps_table(rows))
    parts.append("</section>")
    return "\n".join(parts)


FLOWS = [
    ("A1", "Alur A · Penjualan normal (Order-to-Cash) · 1/4", "A1 — Sales membuat pesanan di POS", A.a1, A.A1_ROWS,
     ["Hari 1 · 09.00–09.50", "Sales", "Data D-01 · D-04"],
     "Titik awal semua penjualan. Sales memutuskan **jenis pesanan** (biasa / sample / khusus), qty final bersama pelanggan, termin bayar, kebutuhan QC dan cara pemenuhan. Hasilnya satu **SO berstatus Dicadangkan** yang mengunci roll selama 3 hari.",
     [("a", "Keputusan di langkah ini", ["Jenis pesanan: Biasa → A2 · Sample → **E** · Khusus → **F** (K01)", "Qty ≠ roll utuh → genapkan atas/bawah/potong (K02)", "Harga nego → **Minta Harga Khusus (B)** (K03)", "Kirim atau **Ambil di Gudang** (K06)"]),
      ("", "Aturan sistem", ["Diskon manual tidak ada — potongan hanya lewat Harga Khusus", "Sample tidak boleh dicampur baris biasa", "Stok kurang → ditolak kecuali izin backorder", "PPN 12% × DPP 11/12 (efektif 11%) untuk PT PKP"]),
      ("g", "Bukti minimal", ["Nomor SO + tangkapan Review (Grand Total)", "Qty diminta vs qty final", "Termin & request QC yang dipilih"]),
      ("r", "Temuan pra-UAT terkait", ["**F-03** grade/LOT ikut terkirim ke akun Sales lewat API", "**F-02** '0 roll tersedia' dari strip *Sering dibeli*", "**F-04** kartu *Jml Tersedia* menjumlah yard + kg"])]),
    ("A2", "Alur A · Penjualan normal · 2/4", "A2 — Verifikasi Admin Sales, persetujuan & konfirmasi", A.a2, A.A2_ROWS,
     ["Hari 1 · 09.50–10.30", "Admin Sales", "Manajer"],
     "Pemisahan tugas: **Admin Sales memeriksa kelengkapan**, **Manajer memutus nilai/kredit/harga**, lalu **Admin Sales mengonfirmasi** sehingga tugas gudang lahir. Urutan ini ditegakkan server — konfirmasi sebelum verifikasi atau sebelum disetujui selalu ditolak.",
     [("a", "Gerbang persetujuan", ["**Harga khusus** → manajer (B1)", "**Kredit** over-limit / tunggakan → manajer (B2)", "**Nilai** di atas ambang (Aturan Persetujuan)", "**Stok cadangan makloon** dipakai → manajer"]),
      ("", "Siapa boleh apa", ["Sales: membuat & mengajukan, **tidak** menyetujui", "Admin Sales: verifikasi, ajukan, konfirmasi, override", "Manajer: setujui / tolak per entri", "Pengaju harga ≠ pemutus"]),
      ("g", "Bukti minimal", ["Checklist verifikasi (nama & waktu)", "Entri persetujuan + pemutus + catatan", "Nomor tugas gudang setelah konfirmasi"]),
      ("r", "Uji negatif wajib", ["Konfirmasi sebelum verifikasi → 409", "Sales/Admin Sales klik setujui → 403", "Konfirmasi dua kali → tidak ada tugas ganda"])]),
    ("A3", "Alur A · Penjualan normal · 3/4", "A3 — Gudang: potong, pick, QC, cek muat & Surat Jalan", A.a3, A.A3_ROWS,
     ["Hari 1 · 10.45–11.35", "Gudang", "Admin Gudang", "QC"],
     "Roll yang dikirim harus **roll yang dipindai**. Sistem memblokir roll asing, roll belum dipotong, muatan yang tidak cocok manifest, dan SO yang meminta QC tetapi belum lulus. Surat Jalan terbit **per keberangkatan**, bukan per SO.",
     [("a", "Keputusan gudang", ["Reservasi potong? → potong + label anak (K18)", "SO minta QC? → SPK QC pesanan (K05)", "Muatan tidak cocok / tanpa tag → pengecualian (K19)", "Kirim sebagian bila kebijakan mengizinkan"]),
      ("", "Dokumen yang terbit", ["Surat Pengambilan Barang (picking list)", "Label roll anak hasil potong", "Hasil Final Loading Check", "**Surat Jalan KSC/SJ-xxxxx**"]),
      ("g", "Bukti minimal", ["Picking list + roll yang dipindai", "Panjang induk sebelum/sesudah potong", "Nomor SJ + qty per roll"]),
      ("r", "Temuan pra-UAT terkait", ["**F-05** sesudah potong, alokasi SO masih menunjuk roll **induk**", "**F-10** SO CBD tetap bisa dikirim sebelum bayar"])]),
    ("A4", "Alur A · Penjualan normal · 4/4", "A4 — Pengiriman sampai diterima pelanggan", A.a4, A.A4_ROWS,
     ["Hari 1 · 11.35–12.15", "Admin Gudang", "Sopir / ekspedisi", "Admin Sales"],
     "Satu pengiriman boleh membawa **beberapa SJ dan beberapa SO**. Bukti wajib di setiap tahap: foto muat sebelum *Dimuat*, resi atau plat+sopir sebelum *Berangkat*, foto POD + nama penerima sebelum *Terkirim*. Pengambilan sendiri diserahkan hanya dengan **kode pickup**.",
     [("a", "Keputusan logistik", ["Ekspedisi · Armada sendiri · Diambil pelanggan (K20)", "Gagal kirim → alasan → jadwalkan ulang (K21)", "Ongkir: ditanggung KN / dibayar pelanggan"]),
      ("", "Status pengiriman", ["Disiapkan → Dimuat → Dalam perjalanan → Terkirim → Selesai", "Ambil sendiri: Menunggu diambil → Diserahkan → Selesai", "Gagal kirim → Disiapkan (jadwal ulang)"]),
      ("g", "Bukti minimal", ["Nomor LG + foto muat & POD", "Nama penerima / pengambil + identitas", "SO berstatus **Selesai**"]),
      ("r", "Temuan pra-UAT terkait", ["**F-06** POD tidak menutup SO — Admin Sales menandai lagi", "**F-07** Perjalanan Pesanan *Disiapkan gudang 0/1*"])]),
    ("B1", "Alur B · Persetujuan & harga · 1/2", "B1 — Harga khusus: ajukan, putuskan, ajukan ulang", BC.b1, BC.B1_ROWS,
     ["Hari 1 · 13.15–13.50", "Sales", "Admin Sales", "Manajer"],
     "Harga di bawah pricelist **hanya** lewat Harga Khusus yang disetujui manajer — bukan diskon. Pengajuan menempel pada **versi alokasi** (roll & qty); bila Admin Sales mengubah alokasi, harga harus diajukan ulang. Harga tetap per pelanggan dikelola terpisah di *Harga per Pelanggan*.",
     [("a", "Keputusan", ["Manajer: setujui / tolak (K10)", "Sales: ajukan ulang atau batalkan", "Admin Sales: ubah alokasi → ajukan ulang (K11)"]),
      ("", "Lapisan harga", ["Harga langganan pelanggan → harga per badan usaha → harga global", "Harga khusus per pesanan (persetujuan) menang", "OD: harga terkunci per item (F19)"]),
      ("g", "Bukti minimal", ["Harga normal vs diminta + alasan + bukti", "Pemutus & catatan", "Total SO sebelum/sesudah"]),
      ("r", "Temuan pra-UAT", ["**F-09** setelah ditolak lalu diajukan ulang & disetujui, SO tetap terkunci — langkah B06 diperkirakan **Gagal**"])]),
    ("B2", "Alur B · Persetujuan & harga · 2/2", "B2 — Kredit over-limit, ambang nilai & stok makloon", BC.b2, BC.B2_ROWS,
     ["Hari 1 · 13.50–14.15", "Sales Kanda", "Admin Sales", "Manajer", "Finance"],
     "Limit kredit dihitung dari **eksposur** (piutang + SO terbuka) dan tunggakan. Pelanggaran tidak memblokir pembuatan SO, tetapi SO **tidak bisa disetujui** sampai manajer memutus entri kredit. Ambang nilai dan pemakaian stok cadangan makloon memakai mekanisme yang sama.",
     [("a", "Keputusan", ["Kredit: setujui (hold dilepas) / tolak (K08)", "Ditolak → DP/CBD, kurangi qty, lunasi tunggakan"]),
      ("", "Aturan", ["Override kredit sekali pakai", "Verifikasi menampilkan kredit sebagai peringatan", "Ambang nilai = pengaturan global (uji di jendela khusus)"]),
      ("g", "Bukti minimal", ["Limit, eksposur & alasan entri kredit", "Keputusan + bukti persetujuan", "SO berubah Disetujui"]),
      ("r", "Temuan pra-UAT", ["**F-09** juga berlaku untuk entri kredit yang ditolak"])]),
    ("C1", "Alur C · Stok kurang", "C1 — Backorder & rencana pemenuhan multi-sumber", BC.c1, BC.C1_ROWS,
     ["Hari 1 · 15.15–15.55", "Sales", "Admin Sales", "CST", "Pembelian"],
     "Sales melihat stok global, tetapi SO hanya boleh mencadangkan **stok milik badan usaha penjual**. Kekurangan dipenuhi lewat dokumen resmi yang tertaut ke SO: stok sendiri di gudang lain, **transaksi antar-PT**, **PR → PO supplier**, atau menunggu PO berjalan. Barang yang lulus QC otomatis dicadangkan ke SO.",
     [("a", "Keputusan", ["Sumber per baris: stok sendiri · PT lain · supplier · tunggu (K12)", "Penuh atau sebagian; sisa tetap backorder"]),
      ("", "Aturan", ["Total rencana ≤ kekurangan", "Ulang tidak menggandakan PR/PIN", "Owner pindah ≠ barang tiba", "Harga internal wajib untuk antar-PT"]),
      ("g", "Bukti minimal", ["SO + nomor PIN/IC/PR/PO", "Owner & lokasi sebelum/sesudah", "Qty dicadangkan setelah barang masuk"]),
      ("r", "Belum diuji pra-UAT", ["Serah terima barang oleh CST & penerimaan di gudang pembeli (C07)"])]),
    ("D1", "Alur D · Pengadaan & penerimaan · 1/2", "D1 — PR → PO supplier atau Order Makloon", DE.d1, DE.D1_ROWS,
     ["Hari 2 · 10.15–10.30", "Pembelian", "Manajer", "Supplier / mitra"],
     "Pengadaan selalu berawal dari **PR** yang merujuk kebutuhan (SO, OD, restock). Jalur per baris: **beli barang jadi ke supplier** (PO) atau **makloon** (bahan dikeluarkan ke mitra, hasil aktual diterima kembali). Reservasi bahan bukan pengeluaran, dan pengeluaran bukan hasil.",
     [("a", "Keputusan", ["PR ≥ Rp50 jt / PO ≥ Rp100 jt → ACC manajer (K13)", "Jalur supplier / makloon (K14)"]),
      ("", "Aturan", ["Default jalur dari master restock artikel", "Realisasi ulang tidak menggandakan PO", "Qty belum diterima = incoming, bukan stok"]),
      ("g", "Bukti minimal", ["Nomor PR, PO / MKO & asal SO/OD", "Supplier, qty, unit, gudang terima", "Stok bahan awal/akhir (makloon)"]),
      ("r", "Belum diuji pra-UAT", ["Order Makloon, pengeluaran bahan & hasil aktual", "Hutang supplier: kontrabon & pembayaran"])]),
    ("D2", "Alur D · Pengadaan & penerimaan · 2/2", "D2 — Kedatangan barang, hitung fisik, MD Quality, QC & stok", DE.d2, DE.D2_ROWS,
     ["Hari 2 · 10.30–11.30", "Admin Gudang", "Gudang", "MD Quality", "QC"],
     "Stok yang masuk adalah **hasil hitung fisik** per roll, bukan qty pesanan. Selisih dengan SJ wajib diputus sebelum ditutup. Barang masuk karantina; **MD Quality** menilai warna/handfeel terhadap sample ACC dan **QC** menilai cacat 4-point — dua penilaian berbeda — lalu keputusan manusia melepas barang menjadi stok tersedia.",
     [("a", "Keputusan", ["Selisih: terima dengan catatan / klaim / tolak (K15)", "SPK: terima · sebagian · turun grade · tolak · tahan (K16)", "Karantina: terima / tolak → Nota Debit (K17)"]),
      ("", "Aturan", ["Penerimaan bruto dari fisik sebelum dipotong", "Potongan uji MDQ = pemakaian", "Interval QC selalu yard walau stok kg"]),
      ("g", "Bukti minimal", ["SJ terkoreksi, jumlah roll & qty fisik", "Selisih & keputusannya", "Hasil MDQ + QC, status roll akhir"]),
      ("r", "Temuan pra-UAT", ["**F-14** SPK ditutup *terima*, roll tetap karantina sampai keputusan kedua", "**F-13** MDQ bisa mengisi saat SPK draf"])]),
    ("E1", "Alur E · Sample", "E1 — Pesanan sample: standar, hanger, catalogue; gratis/berbayar", DE.e1, DE.E1_ROWS,
     ["Hari 1 · 15.55–16.35", "Sales", "Finance", "Admin Sample", "Gudang"],
     "Sample adalah pesanan **terpisah** (nomor SOS) dengan batas panjang per jenis. Sample berbayar harus disetujui pembayarannya sebelum diteruskan ke gudang. Gudang memotong dari roll yang dipindai dan mencatat **panjang aktual**; potongan diserahkan ke Admin Cutting sebelum dikirim. Potongan ecer berbayar di atas batas = **pesanan biasa**.",
     [("a", "Keputusan", ["Dalam batas sample? (K23)", "Gratis / berbayar → Setujui Bayar (K24)", "Warna soft catalogue (Admin Sample)"]),
      ("", "Batas", ["Standar: woven 5 yd · knit 2 kg", "Hanger: woven 0,5 yd", "Catalogue: 1 yd/warna tersedia + 2 yd satu warna soft"]),
      ("g", "Bukti minimal", ["Nomor SOS & jenis", "Panjang aktual, roll induk & anak", "Serah terima Admin Cutting, SJ"]),
      ("r", "Temuan pra-UAT", ["**F-15** nilai berubah setelah potong aktual sesudah *Setujui Bayar*"])]),
    ("F1", "Alur F · Pesanan Khusus · 1/4", "F1 — Permintaan custom multi-item, persetujuan & routing", F.f1, F.F1_ROWS,
     ["Hari 2 · 08.30–08.50", "Sales", "Manajer"],
     "Pesanan Khusus (OD) dipakai untuk produk yang **belum ada**. Satu OD boleh berisi beberapa item dengan sumber & jenis uji berbeda. Setelah disetujui, sistem membagi pekerjaan otomatis: printing ke **Desainer**, labdip/handfeel ke **R&D**. OD berakhir saat dikonversi menjadi SO dan SO itu selesai.",
     [("a", "Keputusan", ["Rantai ACC OD (K25)", "Jenis permintaan menentukan rute (K26)"]),
      ("", "Sumber item", ["Induk produk existing (custom warna)", "Desain existing belum jadi produk", "Desain dari pelanggan · desain baru"]),
      ("g", "Bukti minimal", ["Nomor OD, item A100 & B200", "Referensi per item", "Tugas penerima (DSR / sample)"]),
      ("r", "Status kandidat", ["Modul OD berubah selama penyusunan (FE-01 lanjutan, a3f7936) — belum diuji pra-UAT; uji di kandidat beku"])]),
    ("F2", "Alur F · Pesanan Khusus · 2/4", "F2 — Ronde desain, Print paper & ACC PIC", F.f2, F.F2_ROWS,
     ["Hari 2 · 08.50–09.15", "MD", "Desainer", "PIC"],
     "Desainer bekerja per **ronde**; *Print paper* adalah checklist aktivitas cetak per ronde, **bukan** persetujuan. Cukup **satu PIC** berwenang yang memberi ACC beserta **nilai desain**. Revisi wajib beralasan dan menjaga riwayat ronde lama; perubahan motif utama menjadi OD *redesign* baru.",
     [("a", "Keputusan", ["PIC: ACC + nilai · revisi · tahan (K27)", "Motif berubah → redesign (K28)"]),
      ("", "Aturan", ["Serah hasil menunjuk artwork nyata", "HOLD tidak bisa dipakai proofing", "Nilai desain ≠ nilai penjualan"]),
      ("g", "Bukti minimal", ["Versi v1/v2 + checklist per ronde", "Alasan revisi", "ACC & nilai oleh satu PIC"]),
      ("r", "Status kandidat", ["Modul OD berubah selama penyusunan (a3f7936) — belum diuji pra-UAT"])]),
    ("F3", "Alur F · Pesanan Khusus · 3/4", "F3 — Sampling R&D, keputusan pelanggan & reproofing", F.f3, F.F3_ROWS,
     ["Hari 2 · 09.15–09.40", "R&D", "Supplier", "Admin Sales", "Pelanggan"],
     "R&D mengirim permintaan sample ke beberapa supplier, menilai hasil dan memilih pemenang. **ACC pelanggan** adalah keputusan terpisah dari ACC internal: revisi pelanggan memicu **reproofing** dengan artwork yang sama sampai ACC.",
     [("a", "Keputusan", ["Pemenang sample (K29)", "Pelanggan: ACC · revisi · tolak (K30)"]),
      ("", "Aturan", ["Jenis uji wajib mengikuti lini produk", "Satu ACC tidak meluluskan jenis wajib lain", "Ronde lama tetap tercatat"]),
      ("g", "Bukti minimal", ["Hasil per supplier/jenis/ronde", "Bukti keputusan pelanggan", "Sample pemenang"]),
      ("r", "Status kandidat", ["Modul OD berubah selama penyusunan (a3f7936) — belum diuji pra-UAT"])]),
    ("F4", "Alur F · Pesanan Khusus · 4/4", "F4 — Kunci harga, SKU, pengadaan per item & konversi ke SO", F.f4, F.F4_ROWS,
     ["Hari 2 · 09.40–10.00", "Admin Sales", "MD", "Pembelian"],
     "Setelah pelanggan ACC: harga final **dikunci per item** (kontrak supplier pemenang + margin, acuan Grade A induk), SKU varian dibuat eksklusif untuk pelanggan, tiap item dipenuhi lewat supplier atau makloon, lalu OD diubah menjadi **SO** yang mempertahankan item A & B beserta harganya.",
     [("a", "Keputusan", ["Harga ≥ acuan? tidak → Special Price (K31)", "Jalur item: supplier / makloon (K32)"]),
      ("", "Aturan", ["Konversi ulang tidak membuat SO kedua", "SKU OD hanya untuk pelanggan pemilik", "Status OD mengikuti SO"]),
      ("g", "Bukti minimal", ["Harga terkunci per item + margin", "SKU, PR/PO/MKO per item", "SO hasil vs OD per item"]),
      ("r", "Status kandidat", ["Modul OD berubah selama penyusunan (a3f7936) — belum diuji pra-UAT"])]),
    ("G1", "Alur G · Logistik & transit", "G1 — Multi-gudang, konsolidasi transit & leg Jakarta", GHI.g1, GHI.G1_ROWS,
     ["Hari 2 · 11.30–12.15", "Gudang", "Admin Gudang", "Sopir"],
     "Satu lokasi (Rancamalang) punya banyak gudang. Barang di-pick per gudang, dikumpulkan di **Gudang Transit**, divalidasi sebagai satu muatan, lalu berangkat. Tujuan pertama bisa **transit Jakarta**: penerimaan Jakarta bukan POD pelanggan, dan pengiriman lanjutan memakai **SJ baru**. Tiga dimensi selalu dibedakan: lokasi fisik, pemilik, SO yang dipenuhi.",
     [("a", "Keputusan", ["Tujuan pertama: pelanggan / transit Jakarta (K22)"]),
      ("", "Aturan", ["SJ per SO per keberangkatan", "Manifest memuat seluruh muatan", "Transfer internal tidak mengubah owner"]),
      ("g", "Bukti minimal", ["Picking per gudang", "Serah terima transit & manifest", "Bukti keluar–tiba–kirim lanjut"]),
      ("r", "Keputusan tertunda", ["**DES-02** penamaan & pengelompokan dokumen per leg — G05–G07 dapat **Terblokir**"])]),
    ("H1", "Alur H · Retur · 1/2", "H1 — Pengajuan retur, perjalanan Jakarta → Rancamalang & QC", GHI.h1, GHI.H1_ROWS,
     ["Hari 2 · 13.15–14.10", "Sales", "Manajer", "Gudang JKT/RCM", "QC"],
     "Retur hanya untuk roll yang **benar-benar terkirim**. Persetujuan manajer di awal hanya **izin barang kembali untuk diperiksa**. Barang dapat diterima di Jakarta, dikirim ke **area transit QC Rancamalang**, dan baru diperiksa QC setelah tiba. Lokasi berubah hanya lewat scan berdokumen; pemilik tidak berubah karena pindah lokasi.",
     [("a", "Keputusan", ["Klaim valid? (K33)", "Izinkan barang kembali (K34)"]),
      ("", "Aturan owner", ["21 hari dari SJ s/d tanggal pengajuan (KLR-09)", "Foto boleh menyusul (kebijakan)", "Sebab keluhan dari master"]),
      ("g", "Bukti minimal", ["SO/SJ/roll & qty klaim", "Dokumen TRM / SJ / TBA per scan", "Hasil QC per roll"]),
      ("r", "Temuan pra-UAT", ["**F-11** Gudang & QC ditolak 403", "**F-12** QC bisa tanpa barang diterima"])]),
    ("H2", "Alur H · Retur · 2/2", "H2 — Cutloss, kompensasi, keputusan akhir, disposisi & pengganti", GHI.h2, GHI.H2_ROWS,
     ["Hari 2 · 14.10–14.45", "MD Quality", "Finance", "Manajer", "Admin Sales", "CST"],
     "Keputusan akhir **setelah QC**. Nilai kompensasi diputus **Finance** (harga transaksi awal × qty), outcome diselesaikan **Manajer** dengan bukti. Barang yang kembali diputus pemiliknya: Sukacita simpan atau kembalikan ke CST; CST wajib menerima lalu simpan, retur ke supplier, atau buang BS. Tukar barang berlanjut sebagai SO pengganti sampai POD.",
     [("a", "Keputusan", ["Outcome: refund · saldo · nego · tukar · tolak (K35)", "SO asal lunas? (K36)", "Tujuan barang (K37) · tindak lanjut CST (K38)"]),
      ("", "Aturan owner (KLR)", ["Cutloss: kompensasi = qty cacat (01/02)", "Tukar dihitung yard aktual QC; lebih dibayar pelanggan (03–05)", "Diskon foto/video, nominal per item, Finance memutus (06–08)", "Ongkir: penanggung per kasus (11)"]),
      ("g", "Bukti minimal", ["Qty cacat & dasar nilai", "Bukti keputusan + peran", "Disposisi per roll & dokumen pasangan"]),
      ("r", "Belum diuji pra-UAT", ["Cutloss & pecah roll, pesanan pengganti, Retur Antar-PT & ke Supplier"])]),
    ("I1", "Alur I · Penagihan & pembayaran", "I1 — Termin, faktur pajak, kwitansi, selisih sampai LUNAS", GHI.i1, GHI.I1_ROWS,
     ["Hari 1 · 14.15–15.00", "Finance", "Admin Sales", "Sales", "Manajer"],
     "Proses penjualan baru tuntas saat **pembayaran lunas**. Termin menentukan apakah uang masuk sebelum atau sesudah kirim. Finance menerbitkan Faktur Pajak (PT PKP), mencatat kwitansi dan mengalokasikannya ke SO; kurang bayar tetap ditagih, lebih bayar diputus (deposit/refund/alokasi). Admin Sales mengejar jatuh tempo, Sales hanya melapor.",
     [("a", "Keputusan", ["Bayar sebelum kirim? (K39)", "Pembayaran vs tagihan (K40)", "Di luar wewenang → manajer"]),
      ("", "Aturan", ["Tunai → Kas Kecil; transfer/giro/QRIS → Bank", "Faktur pajak hanya sekali (Pengganti untuk revisi)", "Pendapatan diakui saat barang keluar"]),
      ("g", "Bukti minimal", ["FKT (DPP/PPN), kwitansi AR", "Status bayar Sebagian → Lunas", "Keputusan selisih"]),
      ("r", "Temuan pra-UAT", ["**F-10** CBD/DP tidak menahan kirim", "**F-16** jatuh tempo dari tanggal SO", "**F-08** dokumen tagihan resmi"])]),
]


def all_rows():
    groups = []
    for fl in FLOWS:
        groups.append((fl[2], [(r[0], r[3] if r[3] and r[3] != "—" else r[2]) for r in fl[4]]))
    groups.append(("J — Akses per peran", [(a[0], f"{a[1]}: uji positif & negatif akses") for a in back.ACCESS]))
    groups.append(("K — Konsistensi data", [(k[0], k[1]) for k in back.CONSIST]))
    return groups


def all_sections():
    pages = {}
    if os.path.exists(PAGES_JSON):
        pages = json.load(open(PAGES_JSON, encoding="utf-8"))
    entries = [
        ("", "Cara memakai panduan ini", pages.get("Cara memakai panduan ini", "")),
        ("", "Peta besar end-to-end", pages.get("Satu rantai end-to-end: dari kebutuhan sampai lunas", "")),
        ("", "Daftar 40 titik keputusan", pages.get("Daftar 40 titik keputusan & ke mana tiap pilihan pergi", "")),
        ("", "Jadwal Hari 1 & Hari 2", pages.get("Hari 1 — Order-to-Cash: dari pesanan sampai lunas", "")),
        ("", "Kesiapan & aturan pelaksanaan", pages.get("Kesiapan sebelum hari UAT, peran sesi & aturan pelaksanaan", "")),
        ("", "Data uji, akun & konfigurasi", pages.get("Data acuan, akun per peran & konfigurasi yang mempengaruhi hasil", "")),
    ]
    for fl in FLOWS:
        entries.append((fl[0], fl[2].split("— ", 1)[1], pages.get(fl[2], "")))
    entries += [
        ("J·K", "Akses per peran & konsistensi data", pages.get("J — Akses per peran · K — Konsistensi data & laporan", "")),
        ("", "Hasil uji pra-UAT", pages.get("Hasil uji tim IT sebelum UAT (21 Oktober 2026)", "")),
        ("", "17 temuan & akar masalah", pages.get("17 temuan dari uji pra-UAT — akar masalah & rencana perbaikan", "")),
        ("", "Rencana perbaikan & keputusan tertunda", pages.get("Rencana perbaikan bertahap & keputusan yang masih ditunggu", "")),
        ("", "Lembar hasil per langkah", pages.get("Lembar hasil per langkah", "")),
        ("", "Berita acara & form temuan", pages.get("Berita acara UAT", "")),
    ]
    out = [front.cover(), front.toc(entries), front.reading(), front.big_map(), front.decisions()]
    out += sched.schedule()
    out += [sched.readiness(), sched.data_page(), sched.config_page()]
    for code, kicker, title, fn, rows, chips, lead, info in FLOWS:
        out.append(flow_page(kicker, title, fn(), rows, chips, lead, info))
    out += [back.access_page(), back.tests_page(), back.findings_pages(), back.plan_page()]
    out += back.result_sheet(all_rows())
    out.append(back.signoff())
    return out


TITLES = (["Cara memakai panduan ini", "Satu rantai end-to-end: dari kebutuhan sampai lunas",
           "Daftar 40 titik keputusan & ke mana tiap pilihan pergi", "Hari 1 — Order-to-Cash: dari pesanan sampai lunas",
           "Kesiapan sebelum hari UAT, peran sesi & aturan pelaksanaan",
           "Data acuan, akun per peran & konfigurasi yang mempengaruhi hasil"]
          + [fl[2] for fl in FLOWS]
          + ["J — Akses per peran · K — Konsistensi data & laporan", "Hasil uji tim IT sebelum UAT (21 Oktober 2026)",
             "17 temuan dari uji pra-UAT — akar masalah & rencana perbaikan",
             "Rencana perbaikan bertahap & keputusan yang masih ditunggu",
             "Lembar hasil per langkah", "Berita acara UAT"])
