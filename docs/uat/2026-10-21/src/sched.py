"""Jadwal 2 hari, kesiapan, data uji & akun."""
from html import escape
from page import head, fmt

# (waktu, menit, judul sesi, tujuan, [aktivitas], peran, data, output)
DAY1 = [
    ("08.00–08.30", 30, "Persiapan tim (sebelum peserta)", "Kandidat beku & semua akun siap.",
     ["Catat URL, commit, perubahan lokal & konfigurasi; **bekukan** kandidat selama hari uji.",
      "Uji login 12 akun peran (sandi dibagikan terpisah; lihat F-01).",
      "Cek data acuan: stok DENIM TENCEL di Jakarta, ALICE KNIT hanya di CST, limit kredit CV Garmen Soreang Jaya Rp25 jt.",
      "Siapkan printer PDF/label, handheld RFID (bila tidak ada: Admin Gudang siap memberi pengecualian), folder bukti per alur."],
     "Fasilitator, IT", "Daftar akun, data D-01…D-07", "Daftar periksa kesiapan ✓"),
    ("08.30–09.00", 30, "Pembukaan & akses (J)", "Peserta paham peta besar & bisa masuk mejanya.",
     ["Fasilitator membacakan tujuan, peta besar & 40 titik keputusan (hal. peta & percabangan).",
      "Aturan status Lulus/Gagal/Terblokir/Tidak diuji; cara mengisi lembar hasil.",
      "Setiap peserta login dengan akun perannya, buka **Meja Saya** / meja perannya (J01–J04).",
      "Uji cepat: Sales tidak melihat menu Operasi Gudang; Desainer hanya melihat menu desain."],
     "Semua", "Akun per peran", "Semua peserta login; tangkapan menu per peran"),
    ("09.00–09.50", 50, "A1 · Sales membuat pesanan", "SO terbentuk benar untuk 4 varian pesanan.",
     ["**SO-1**: Toko Kain Sejahtera, DENIM TENCEL TAUPE 150 yd (mode qty), NET30 → periksa harga, PPN, total (A02–A06).",
      "**SO-2**: 300 yd → **Genapkan ke roll utuh**, pelanggan pilih atas/bawah (A04).",
      "**SO-3**: Ambil di Gudang besok (tanggal wajib) (A06).",
      "**SO-4**: Request **QC seluruh roll** (A05).",
      "Negatif: campur sample, qty 0, ambil tanpa tanggal, stok kurang tanpa backorder (A07)."],
     "Sales, (pelanggan diperankan pemilik proses)", "D-01, D-04", "Nomor SO-1…SO-4 + tangkapan Review"),
    ("09.50–10.30", 40, "A2 · Verifikasi, ACC & konfirmasi", "Urutan verifikasi → ACC → konfirmasi ditegakkan.",
     ["Admin Sales: konfirmasi SO-1 **sebelum** verifikasi → harus ditolak (A11 negatif).",
      "Verifikasi SO-1…SO-4 (A08); satu SO dibuat cacat alamat → verifikasi ditolak → lengkapi (A08b).",
      "Ajukan persetujuan → auto-approve (A09); Sales & Admin Sales mencoba menyetujui → 403 (A10).",
      "Konfirmasi (A11) → cek tugas gudang lahir per gudang; konfirmasi ulang tidak menggandakan."],
     "Admin Sales, Manajer, Sales", "SO-1…SO-4", "SO Dikonfirmasi + nomor tugas gudang"),
    ("10.30–10.45", 15, "Istirahat", "", [], "", "", ""),
    ("10.45–11.35", 50, "A3 · Gudang: potong, pick, QC, muat, SJ", "Roll yang dikirim = roll yang dipindai.",
     ["SO-1: konfirmasi **potong** roll yang dicadangkan sebagian, cetak & verifikasi label anak (A13); pick mengikuti daftar alokasi (uji **F-05**).",
      "Scan pick roll asing → ditolak (A14).",
      "SO-4: Admin Gudang tugaskan SPK QC, QC isi 4-point, coba kirim sebelum lulus → ditolak (A15).",
      "SO-3: tugas *ditahan* → [[Rilis ke Antrean]] → pick.",
      "Final Loading Check; tanpa tag → pengecualian Admin Gudang (A16); [[Kirim]] → SJ (A17)."],
     "Gudang, Admin Gudang, QC", "SO-1, SO-3, SO-4", "Nomor SJ per SO + panjang induk sebelum/sesudah"),
    ("11.35–12.15", 40, "A4 · Pengiriman sampai diterima", "Bukti tiap tahap kirim & penerimaan.",
     ["LG-1 ekspedisi untuk SO-1: tanpa resi tidak bisa berangkat → isi resi (A18–A20).",
      "LG-2 armada sendiri berisi SO-2 + SO-4 (2 SO satu kendaraan); foto muat, berangkat, POD (A19–A21).",
      "Simulasi **gagal kirim** → alasan → jadwal ulang (A20b).",
      "SO-3 diambil pelanggan: kode salah ditolak, kode benar diserahkan (A22).",
      "Admin Sales **Tandai diterima** semua SO (A23); cek status Selesai (uji **F-06**)."],
     "Admin Gudang, Sopir, Admin Sales", "SJ dari A3", "Nomor LG, foto muat/POD, SO Selesai"),
    ("12.15–13.15", 60, "Istirahat", "", [], "", "", ""),
    ("13.15–14.15", 60, "B · Gerbang harga khusus & kredit", "Harga & kredit hanya berubah lewat keputusan sah.",
     ["**SO-5**: Minta Harga Khusus (alasan kosong → ditolak) → verifikasi → manajer **setujui** → total dihitung ulang (B01–B05).",
      "**SO-6**: harga khusus **ditolak** → Sales ajukan ulang → manajer setujui → SO harus lanjut (uji **F-09**).",
      "**SO-7**: Admin Sales **Ganti Roll** setelah harga diajukan → keputusan lama ditolak sistem (B07).",
      "Pemisahan tugas: manajer yang mengajukan tidak bisa memutus sendiri.",
      "**SO-8 kredit**: Sales Kanda, CV Garmen Soreang Jaya 700 kg LYFLEX (> Rp25 jt) → credit hold → manajer putuskan (B11–B16)."],
     "Sales, Admin Sales, Manajer", "D-01, D-02, D-06", "Entri persetujuan + pemutus + total sebelum/sesudah"),
    ("14.15–15.00", 45, "I · Penagihan & pembayaran sampai lunas", "SO-1 lunas dengan dokumen pajak & kwitansi benar.",
     ["Finance: **Siap terbitkan Faktur Pajak** SO-1 → terbitkan; ulang → ditolak (I03).",
      "Admin Sales cetak Faktur Komersial & SJ (I04).",
      "Finance catat kwitansi 50% → *Sebagian*; alokasi melebihi sisa → ditolak; pelunasan → *Lunas* (I06).",
      "Lebih bayar di SO-2 → keputusan selisih (deposit/refund) (I07).",
      "**SO-9 CBD**: coba kirim sebelum bayar (uji **F-10**); cek daftar jatuh tempo (uji **F-16**)."],
     "Finance, Admin Sales, Gudang", "SO-1, SO-2, SO-9", "FKT, AR (kwitansi), status Lunas"),
    ("15.00–15.15", 15, "Istirahat", "", [], "", "", ""),
    ("15.15–15.55", 40, "C · Stok kurang & rencana pemenuhan", "Kekurangan dipenuhi lewat dokumen yang tertaut.",
     ["**SO-10**: ALICE KNIT 14 100 kg tanpa backorder → ditolak; dengan izin → *Menunggu stok* (C01–C02).",
      "Admin Sales **Atur pemenuhan**: 70 PT lain + 40 supplier → ditolak (lebih); 60 CST + 40 PO → jalan (C03–C04).",
      "Cek PIN & transaksi antar-PT (C05) dan PR dari SO (C06); jalankan ulang → tidak ganda.",
      "PR ini **dibawa ke Hari 2 (D1–D2)** untuk penerimaan."],
     "Sales, Admin Sales, CST", "D-05", "Nomor PIN/IC/PR tertaut SO-10"),
    ("15.55–16.35", 40, "E · Sample", "Jenis & batas sample, potong aktual, serah terima.",
     ["Sample **standar gratis** woven 5 yd; 6 yd → ditolak (E01).",
      "Sample **berbayar** 3 yd: teruskan sebelum disetujui → ditolak; Finance **Setujui Bayar** (E03).",
      "**Catalogue** dari template + 1 warna soft; **hanger** 0,5 yd.",
      "Gudang potong (panjang aktual), Admin Cutting terima, kirim (E05–E07); Finance catat bayar (uji **F-15**)."],
     "Sales, Finance, Admin Sample, Gudang", "D-04", "Nomor SOS, panjang aktual, SJ"),
    ("16.35–17.00", 25, "Rekap Hari 1", "Hasil & temuan tercatat; data Hari 2 siap.",
     ["Isi lembar hasil per langkah; satukan temuan (ID, langkah, bukti).",
      "Pisahkan bug vs keputusan bisnis; tetapkan PIC & target.",
      "Catat dokumen yang dibawa ke Hari 2: PR dari SO-10, SO-1 (untuk retur), SO-3/SO-4."],
     "Fasilitator, pencatat, pemilik proses", "Lembar hasil", "Rekap Hari 1 ditandatangani"),
]

DAY2 = [
    ("08.00–08.30", 30, "Persiapan tim", "Data tahap siap tersedia.",
     ["Pastikan kandidat sama dengan Hari 1 (atau catat versi baru & skenario yang diulang).",
      "Siapkan **OD tahap siap** (sudah di fase *Menunggu ACC pelanggan*) dan **MKO siap terima** sebagai cadangan bila proses fisik tidak selesai dalam sehari.",
      "Siapkan foto SJ supplier contoh, file artwork v1/v2, foto sample."],
     "Fasilitator, IT", "D-08, D-09", "Data tahap siap bertanda"),
    ("08.30–10.00", 90, "F · Pesanan Khusus end-to-end", "Dua item OD bertahan utuh sampai SO.",
     ["F1 (20'): buat OD item **A 100 yd** + **B 200 yd** (sumber berbeda), unggah referensi, ajukan, manajer setujui; cek routing (F02–F06).",
      "F2 (25'): MD tugaskan desainer; artwork v1 + Print paper → PIC **minta revisi** → v2 → **ACC + nilai** (satu PIC cukup); uji **HOLD** & lepas (F07–F12).",
      "F3 (25'): R&D kirim ke supplier, setor hasil, nilai, pilih pemenang; Admin Sales catat **revisi** pelanggan → reproofing → **ACC** (F13–F18).",
      "F4 (20'): kunci harga (margin), buat SKU, pilih jalur per item, realisasi; **Ubah ke Pesanan Penjualan** memakai OD tahap siap (F19–F24)."],
     "Sales, Manajer/PIC, Desainer, MD/R&D, Admin Sales, Pembelian", "D-09", "Nomor OD, DSR, sample, SKU, PR/PO, SO hasil OD"),
    ("10.00–10.15", 15, "Istirahat", "", [], "", "", ""),
    ("10.15–11.30", 75, "D · Pengadaan & penerimaan barang", "Stok masuk = fisik; mutu diputus manusia.",
     ["D1 (15'): realisasi PR dari SO-10 (Hari 1) → PO; MD mencoba realisasi → ditolak; MKO tahap siap (D04–D08b).",
      "D2 (30'): Admin Gudang buat kedatangan, entri SJ & baris; gudang hitung fisik per roll (contoh 10 roll: SJ 1.000 yd, fisik 960 yd); rekonsiliasi selisih; tutup (D10–D14).",
      "D2 (30'): tugaskan SPK; MD Quality warna/handfeel; QC 4-point; keputusan SPK; **keputusan karantina** (uji **F-14**); cek SO-10 otomatis dicadangkan (D15–D20)."],
     "Pembelian, Admin Gudang, Gudang, MD Quality, QC, Manajer", "PR dari SO-10, D-08", "PO, GRN, INS, stok tersedia, SO-10 dicadangkan"),
    ("11.30–12.15", 45, "G · Logistik multi-gudang & transit", "Perjalanan fisik terbaca per roll & per leg.",
     ["SO-11 berisi woven + knitting + printing → pick di 3 gudang Rancamalang (G01).",
      "Transfer ke Gudang Transit, cek muat seluruh muatan, satu LG berisi beberapa SO (G02–G04).",
      "Transit Jakarta: terima di Jakarta, cek muat ulang, SJ baru ke pelanggan (G05–G08) — bila kandidat belum mendukung: **GAP / Terblokir DES-02**, jangan diganti tombol status."],
     "Gudang, Admin Gudang, Sopir", "D-07", "Bukti tiap leg & manifest"),
    ("12.15–13.15", 60, "Istirahat", "", [], "", "", ""),
    ("13.15–14.45", 90, "H · Retur sampai uang / pengganti", "Retur tertelusur dari roll terkirim sampai penyelesaian.",
     ["H1 (20'): Sales retur sebagian dari **SO-1** (Hari 1) + negatif: qty lebih, roll asing, ganti SO cepat, > 21 hari (H02–H03); manajer izinkan (H04).",
      "H1 (20'): **akun Gudang** scan terima Jakarta → kirim → tiba Rancamalang (uji **F-11**); coba QC sebelum terima (uji **F-12**) (H05–H07).",
      "H1 (15'): QC retur per roll: qty aktual, cacat, grade (H08).",
      "H2 (20'): MD Quality cutloss; Finance putus nilai; manajer selesaikan (saldo / refund / nego / tukar); cek pengurangan tagihan (H09–H12).",
      "H2 (15'): tujuan barang: simpan / kembalikan ke CST → CST terima → retur supplier; pesanan pengganti (H13–H17)."],
     "Sales, Manajer, Gudang JKT/RCM, QC, MD Quality, Finance, CST", "SO-1 & SJ-nya", "SRET, dokumen perjalanan, hasil QC, keputusan & bukti"),
    ("14.45–15.00", 15, "Istirahat", "", [], "", "", ""),
    ("15.00–15.45", 45, "J & K · Akses & konsistensi data", "Izin efektif & angka cocok lintas layar.",
     ["Role kustom setara & akun view-only: menu/tombol mengikuti izin; aksi ditolak tanpa mengubah data (J).",
      "Cocokkan Meja vs daftar vs detail (filter sama); Perjalanan Pesanan (uji **F-07**); satuan yard vs kg (uji **F-04**) (K).",
      "Pusat Export: preview vs unduhan vs sumber; data di luar izin tidak bocor (uji **F-03** grade)."],
     "Semua peran", "Dokumen Hari 1–2", "Tangkapan perbandingan angka"),
    ("15.45–16.15", 30, "Uji ulang temuan", "Perbaikan yang masuk saat UAT dibuktikan.",
     ["Bila ada build baru: catat versi, ulangi langkah terdampak saja.",
      "Uji refresh, klik ganda, kirim ulang pada langkah yang diperbaiki."],
     "IT, peserta terkait", "Lembar temuan", "Status retest per temuan"),
    ("16.15–17.00", 45, "Penutupan", "Keputusan lingkup & rencana tindak lanjut.",
     ["Rekap status per alur (Lulus/Gagal/Terblokir/Tidak diuji).",
      "Keputusan bisnis yang muncul → pemilik & tenggat.",
      "Rencana perbaikan & jadwal retest; tanda tangan berita acara."],
     "Pemilik proses, IT, fasilitator", "Lembar hasil & temuan", "Berita acara UAT"),
]


def _sched_table(rows):
    out = ['<table class="grid sched"><colgroup><col style="width:7.5%"><col style="width:4%"><col style="width:15%">'
           '<col style="width:40%"><col style="width:11%"><col style="width:9.5%"><col style="width:13%"></colgroup>'
           '<thead><tr><th>Waktu</th><th>Mnt</th><th>Sesi & tujuan</th><th>Aktivitas berurutan</th><th>Peran aktif</th><th>Data / dokumen</th><th>Output & kriteria selesai</th></tr></thead><tbody>']
    for t, m, title, goal, acts, roles, data, outp in rows:
        if not acts:
            out.append(f'<tr class="brk"><td class="time">{t}</td><td>{m}</td><td colspan="5">{escape(title)}</td></tr>')
            continue
        lis = "".join(f"<li>{fmt(a)}</li>" for a in acts)
        out.append(f'<tr><td class="time">{t}</td><td>{m}</td><td><b>{escape(title)}</b><br><span class="small">{fmt(goal)}</span></td>'
                   f'<td><ol>{lis}</ol></td><td>{fmt(roles)}</td><td>{fmt(data)}</td><td>{fmt(outp)}</td></tr>')
    out.append("</tbody></table>")
    return "".join(out)


def schedule():
    return [
        f'<section class="sec">{head("Jadwal · Hari 1", "Hari 1 — Order-to-Cash: dari pesanan sampai lunas", ["08.00–17.00 WIB", "Alur J · A · B · I · C · E", "Uji efektif 5 jam 45 menit"])}'
        f'<p class="lead">Setiap sesi memakai dokumen yang dibuat sesi sebelumnya (SO-1 dipakai sampai pembayaran dan dibawa ke retur Hari 2). '
        f'Nomor SO-1…SO-10 adalah label kerja — catat nomor sistem yang sebenarnya di lembar hasil.</p>{_sched_table(DAY1)}</section>',
        f'<section class="sec">{head("Jadwal · Hari 2", "Hari 2 — Hulu & hilir: Pesanan Khusus, pengadaan, logistik, retur", ["08.00–17.00 WIB", "Alur F · D · G · H · J · K", "Uji efektif 6 jam"])}'
        f'<p class="lead">Proses fisik yang butuh berhari-hari (produksi supplier/makloon, pengiriman sample, perjalanan Jakarta–Rancamalang) dijalankan '
        f'sampai batas yang bisa dikerjakan dalam sesi; sisanya memakai <b>data tahap siap</b> yang disiapkan pukul 08.00. Tuliskan titik mulai tahap siap di bukti — kelulusan tahap siap tidak meluluskan tahap sebelumnya.</p>{_sched_table(DAY2)}</section>',
    ]


def readiness():
    return f"""<section class="sec">{head("Kesiapan", "Kesiapan sebelum hari UAT, peran sesi & aturan pelaksanaan", ["H-3 s.d. H-0"])}
<table class="grid"><colgroup><col style="width:9%"><col style="width:41%"><col style="width:20%"><col style="width:30%"></colgroup>
<thead><tr><th>Kapan</th><th>Pekerjaan</th><th>PIC</th><th>Bukti siap</th></tr></thead><tbody>
<tr><td><b>H-3</b></td><td>Perbaiki temuan <b>Prioritas 1</b> (F-01, F-03, F-05, F-09, F-10, F-11, F-12) atau sepakati bahwa langkahnya diuji sebagai <i>diperkirakan gagal</i>.</td><td>IT</td><td>Commit + hasil uji regresi per temuan</td></tr>
<tr><td><b>H-2</b></td><td>Restore data acuan (<span class="nav">bash scripts/dev_restore_demo.sh</span>) di lingkungan UAT; samakan sandi akun peran; buat akun role kustom & view-only.</td><td>IT</td><td>12 akun login OK; daftar akun bertanda peran</td></tr>
<tr><td><b>H-2</b></td><td>Periksa konfigurasi yang mempengaruhi uji (tabel di halaman Data uji): verifikasi wajib, kirim sebagian, aturan persetujuan, kebijakan bukti retur, masa reservasi.</td><td>IT + pemilik proses</td><td>Tangkapan Pusat Pengaturan</td></tr>
<tr><td><b>H-1</b></td><td>Siapkan data tahap siap: OD di fase <i>Menunggu ACC pelanggan</i>, MKO siap terima, PO siap diterima dengan SJ contoh; foto SJ, artwork v1/v2, foto sample.</td><td>IT + MD</td><td>Nomor dokumen tahap siap ditandai "TAHAP SIAP"</td></tr>
<tr><td><b>H-1</b></td><td>Perangkat: printer PDF/label, handheld RFID & tag. Bila RFID tidak tersedia, uji kemampuan baca dinyatakan <b>Tidak diuji</b> dan pengecualian berizin dipakai.</td><td>Gudang</td><td>Daftar perangkat</td></tr>
<tr><td><b>H-0</b></td><td>Bekukan kandidat (commit/URL), cetak lembar hasil, siapkan folder bukti per alur (A…K).</td><td>Fasilitator</td><td>Identitas kandidat tercatat</td></tr>
</tbody></table>
<div class="strip">
<div class="box"><b class="t">Pemilik proses / client</b><ul><li>Menilai kesesuaian dengan praktik nyata.</li><li>Memutus keputusan bisnis yang muncul.</li><li>Memerankan pelanggan (ACC sample, pilih genapkan roll, keluhan).</li></ul></div>
<div class="box"><b class="t">Fasilitator</b><ul><li>Menjaga waktu & urutan sesi.</li><li>Menunjuk data tahap siap bila proses terhambat.</li><li>Memastikan setiap peran memakai akunnya.</li></ul></div>
<div class="box"><b class="t">Pengguna per peran</b><ul><li>Menjalankan langkah sendiri di layar.</li><li>Membacakan hasil yang terlihat.</li><li>Tidak memakai akun Admin.</li></ul></div>
<div class="box"><b class="t">Pencatat / IT</b><ul><li>Mencatat nomor dokumen & bukti.</li><li>Mencatat temuan ≤ 5 menit.</li><li>Memisahkan bug vs keputusan bisnis.</li></ul></div>
</div>
<div class="strip c3">
<div class="box g"><b class="t">Kriteria lulus UAT (usulan)</b><ul><li>Seluruh langkah positif alur A, B, C, I <b>Lulus</b> (Order-to-Cash).</li><li>Tidak ada temuan Prioritas 1 terbuka di alur yang dinyatakan siap pakai.</li><li>Langkah Terblokir punya pemilik keputusan & tanggal.</li></ul></div>
<div class="box a"><b class="t">Di luar lingkup</b><ul><li>Tutup buku, jurnal manual, laporan keuangan formal.</li><li>Kinerja perangkat RFID fisik & absensi (HW-01/02).</li><li>Penggajian & SDM.</li></ul></div>
<div class="box r"><b class="t">Jangan</b><ul><li>Mengubah status lewat database.</li><li>Menjalankan dua uji yang mengubah pengaturan global bersamaan.</li><li>Menganggap klik tombol tanpa bukti sebagai lulus.</li></ul></div>
</div></section>"""


ACC = [
    ("Sales", "sales@kainnusantara.id", "Penjualan › POS · Pesanan · Pesanan Khusus · Pesanan Sample · Retur · Meja Saya", "A1, B, C01, E01, F02–F04, H02"),
    ("Sales (Kanda)", "sales.kanda@kainnusantara.id", "sama, badan usaha Kanda Fabric", "B2 kredit"),
    ("Admin Sales", "salesadmin@kainnusantara.id", "Meja Admin Sales · Pesanan · Retur", "A2, A23, B03, B07, C03–C09, F18–F23, I04"),
    ("Admin Sales (Kanda / CST)", "salesadmin.kanda@ · salesadmin.cst@", "Meja Admin Sales badan usahanya", "B2, H15–H16 (CST)"),
    ("Manajer / PIC", "manager@kainnusantara.id", "Pusat Persetujuan · Meja Saya · Pembelian", "A10, B04, B14, D03–D07, F05, F10–F11, H04, H11"),
    ("Finance", "finance@kainnusantara.id", "Meja Finance · Keuangan · Pajak", "E03, H10, H12, I02–I08"),
    ("Gudang", "warehouse@ · warehouse.rancamalang@ · warehouse.soreang@", "Meja Saya · Operasi Gudang", "A12–A17, D12, E05, G, H05–H07"),
    ("Admin Gudang", "wh.admin@kainnusantara.id", "Meja Gudang · Barang Masuk · Pengiriman", "A16b, A18–A22, D10–D18"),
    ("Sopir", "driver@kainnusantara.id", "Pengiriman (kiriman hari ini)", "A19–A21"),
    ("QC", "qc@kainnusantara.id", "QC & Inspeksi", "A15, D17, D19, H08"),
    ("MD Quality", "mdquality@kainnusantara.id", "QC & Inspeksi (Dokumen Inspeksi)", "D16, H09"),
    ("MD / R&D", "md@kainnusantara.id", "Meja MD · R&D · Desainer · Produk & Harga", "D04 (lihat), F07, F13–F16, F20"),
    ("Desainer", "designer@kainnusantara.id", "Desainer › Permintaan Desain · Desain & Pattern", "F08–F09"),
    ("Admin Sample", "sampleadmin@kainnusantara.id", "Meja Sample · Pesanan Sample", "E03–E06"),
]

FIX = [
    ("D-01", "Pelanggan utama", "**Toko Kain Sejahtera** (CUST-0001) · PT Sukacita · Jakarta · alamat *Toko Utama · Pak Hendra* · termin NET30 · belum punya harga langganan.", "A, B1, C, E, H, I"),
    ("D-02", "Pelanggan kredit", "**CV Garmen Soreang Jaya** · Kanda Fabric · limit kredit **Rp25 jt** · tempo.", "B2"),
    ("D-03", "Pelanggan PT lain", "**PT Fashion Ibukota** · Cipta Sandang (CST) · limit Rp600 jt.", "C, H (CST)"),
    ("D-04", "Produk woven (yard)", "**DENIM TENCEL TAUPE / HITAM / BLUE BLACK GARMENT** grade A · Rp19–25 rb/yd · ratusan roll ±120 yd milik Sukacita di *Jakarta · Gudang Sukacita*.", "A, B, E, H"),
    ("D-05", "Produk knit (kg) – stok kurang", "**ALICE KNIT (94139-45) 14 A** · Rp40 rb/kg · stok hanya milik **CST** di *Rancamalang · Gudang Knitting*.", "C, D"),
    ("D-06", "Produk knit Kanda", "**LYFLEX ACTIVE BEIGE A** · Rp41 rb/kg · *Soreang · Gudang Kanda*.", "B2"),
    ("D-07", "Gudang & lokasi", "*Jakarta · Gudang Sukacita* · *Rancamalang · Gudang Transit / Woven / Knitting / Printing / Retur (grade B/BS/C)* · *Soreang · Gudang Kanda*.", "A3, G, H"),
    ("D-08", "Supplier & mitra", "Supplier dari master (mis. *PT Kimia Warna Prima*); mitra makloon & resep proses dari Master Pembelian; SJ supplier contoh (10 roll, SJ 1.000 yd vs fisik 960 yd).", "D"),
    ("D-09", "Pesanan Khusus", "OD dua item: **A 100 yd** (custom warna dari induk) + **B 200 yd** (desain pelanggan, printing); file referensi; artwork v1/v2; dua akun PIC.", "F"),
    ("D-10", "Retur", "SO-1 Hari 1 yang sudah *Selesai* (roll & SJ-nya); contoh tanggal dalam/luar 21 hari.", "H"),
]

CFG = [
    ("Verifikasi Admin Sales sebelum konfirmasi", "`sales_admin.require_verification_before_confirm`", "Hidup", "A08/A11"),
    ("Validasi/ACC nilai SO wajib", "`sales.require_so_validation`", "Mati (auto-approve bila tak ada gerbang)", "A09"),
    ("Ambang persetujuan", "`Pengaturan › Aturan Persetujuan`", "SO: tanpa ambang · PR ≥ Rp50 jt · PO ≥ Rp100 jt · diskon ≥ 10%", "A10, D03, D07"),
    ("Kirim sebagian", "`sales.allow_partial_shipment`", "Hidup", "A17, C09"),
    ("Masa reservasi roll", "otomatis", "3 hari, lalu kedaluwarsa", "A06"),
    ("Pilih roll oleh Sales", "`allocation.roll_pick_sales`", "Periksa (bila mati: hanya Admin Sales lewat Ganti Roll)", "A03"),
    ("Bukti foto retur per tahap", "`returns.evidence_required_*`", "Tidak wajib (submit/approve/inspect/settle)", "H02–H11"),
    ("Masa klaim retur", "Kebijakan Retur", "21 hari dari SJ (pelanggan) · 21 hari dari penerimaan (supplier)", "H03, H17"),
    ("Margin Pesanan Khusus", "pengaturan Special Order", "30% (bawaan)", "F19"),
]


def data_page():
    acc = "".join(f"<tr><td><b>{escape(a)}</b></td><td class='small'>{escape(b)}</td><td>{escape(c)}</td><td>{escape(d)}</td></tr>" for a, b, c, d in ACC)
    fx = "".join(f"<tr><td class='no'>{a}</td><td><b>{escape(b)}</b></td><td>{fmt(c)}</td><td>{escape(d)}</td></tr>" for a, b, c, d in FIX)
    cf = "".join(f"<tr><td>{escape(a)}</td><td>{fmt(b)}</td><td>{escape(c)}</td><td>{escape(d)}</td></tr>" for a, b, c, d in CFG)
    return f"""<section class="sec">{head("Data uji", "Data acuan, akun per peran & konfigurasi yang mempengaruhi hasil", ["Data acuan lokal (restore demo)", "Sandi dibagikan terpisah"])}
<div class="strip c2" style="grid-template-columns: 1.15fr 1fr">
<div><h3 style="margin-top:0">Data uji (fixture)</h3><table class="grid"><colgroup><col style="width:9%"><col style="width:20%"><col style="width:55%"><col style="width:16%"></colgroup>
<thead><tr><th>Kode</th><th>Data</th><th>Isi / patokan</th><th>Dipakai di</th></tr></thead><tbody>{fx}</tbody></table>
<p class="small" style="margin-top:1.5mm">Angka hanya patokan. Selalu catat nomor roll & qty <b>aktual</b> dari layar; hitung ulang total dari roll yang benar-benar dialokasikan.</p></div>
<div><h3 style="margin-top:0">Akun per peran</h3><table class="grid"><colgroup><col style="width:22%"><col style="width:30%"><col style="width:28%"><col style="width:20%"></colgroup>
<thead><tr><th>Peran</th><th>Akun</th><th>Pintu kerja</th><th>Langkah</th></tr></thead><tbody>{acc}</tbody></table></div>
</div>
</section>"""


STAGED = [
    ("TS-1", "OD tahap siap", "Pesanan Khusus 2 item (A/B) dengan sample pemenang sudah diputus, fase *Menunggu ACC pelanggan*.", "F18–F24"),
    ("TS-2", "MKO siap terima", "Order Makloon yang bahannya sudah dikeluarkan; hasil aktual (mis. 192 dari 200 yd) siap diterima.", "D08b, D10–D20"),
    ("TS-3", "PO siap diterima", "PO supplier + foto SJ contoh 10 roll (SJ 1.000 yd, fisik 960 yd) bila PR Hari 1 belum direalisasi.", "D10–D20"),
    ("TS-4", "SO terkirim > 21 hari", "SO dengan SJ lebih dari 21 hari untuk uji negatif tenggat retur.", "H03"),
    ("TS-5", "Retur selesai QC", "Retur yang sudah diterima & QC selesai, untuk uji keputusan/disposisi bila H1 tidak tuntas.", "H09–H17"),
    ("TS-6", "Transfer transit", "Transfer Rancamalang → Jakarta dalam perjalanan untuk uji penerimaan Jakarta.", "G06–G07"),
]


def config_page():
    cf = "".join(f"<tr><td>{escape(a)}</td><td>{fmt(b)}</td><td>{escape(c)}</td><td>{escape(d)}</td></tr>" for a, b, c, d in CFG)
    st = "".join(f"<tr><td class='no'>{a}</td><td><b>{escape(b)}</b></td><td>{fmt(c)}</td><td>{escape(d)}</td></tr>" for a, b, c, d in STAGED)
    return f"""<section class="sec">{head("Data uji", "Konfigurasi yang dicatat sebelum mulai & data tahap siap", ["Catat nilai aktual di kandidat UAT"])}
<table class="grid"><colgroup><col style="width:28%"><col style="width:30%"><col style="width:28%"><col style="width:14%"></colgroup>
<thead><tr><th>Pengaturan</th><th>Kunci / lokasi</th><th>Nilai saat uji pra-UAT</th><th>Langkah terdampak</th></tr></thead><tbody>{cf}</tbody></table>
<h3>Data tahap siap (disiapkan H-1, diberi tanda "TAHAP SIAP")</h3>
<table class="grid"><colgroup><col style="width:7%"><col style="width:18%"><col style="width:60%"><col style="width:15%"></colgroup>
<thead><tr><th>Kode</th><th>Dokumen</th><th>Kondisi yang disiapkan</th><th>Dipakai di</th></tr></thead><tbody>{st}</tbody></table>
<div class="strip c2" style="margin-top:3mm"><div class="box a"><b class="t">Aturan memakai tahap siap</b><ul>
<li>Tulis di bukti: "mulai dari TAHAP SIAP TS-x".</li><li>Kelulusan tahap siap tidak meluluskan tahap sebelumnya — tahap sebelumnya tetap berstatus sesuai pengujiannya.</li>
<li>Jangan memakai nomor dokumen produksi asli sebagai data latihan.</li></ul></div>
<div class="box"><b class="t">Mengubah pengaturan saat UAT</b><ul><li>Hanya bila disepakati pemilik proses & dicatat sebelum/sesudah.</li>
<li>Pengaturan global (ambang persetujuan, kebijakan bukti) diuji di jendela khusus, tidak bersamaan dengan sesi lain.</li></ul></div></div></section>"""
