"""Bagian belakang: akses (J), konsistensi (K), hasil uji pra-UAT, temuan, rencana perbaikan,
keputusan tertunda, lembar hasil, berita acara."""
from html import escape
from page import head, fmt, role_cell

ACCESS = [
    ("J01", "Sales", "POS, Pesanan, Pesanan Khusus, Pesanan Sample, Retur, Pelanggan, Meja Saya",
     "Buat SO/SOS/OD, minta harga khusus & kredit, ajukan retur, lapor Kasus Keuangan",
     "Menyetujui SO/harga (403) · tandai diterima (403) · setujui retur (403) · setujui bayar sample (403) · melihat grade/LOT/pemilik · menu Operasi Gudang", "OK 403; BUG F-03"),
    ("J02", "Admin Sales", "Meja Admin Sales, Pesanan, Retur, Permintaan Internal",
     "Verifikasi, ajukan, konfirmasi, rencana pemenuhan, Ganti Roll, Edit/Override, tandai diterima, cetak SJ/invoice, catat ACC pelanggan OD, kunci harga OD",
     "Menyetujui SO/harga/kredit (403) · keputusan akhir retur (403) · mencatat kwitansi", "OK"),
    ("J03", "Manajer / PIC", "Pusat Persetujuan, Meja Saya, Pembelian",
     "Putuskan nilai/kredit/harga/makloon, PR/PO, retur (izin & akhir), OD, ACC desain", "Memutus pengajuan harga miliknya sendiri", "OK"),
    ("J04", "Finance", "Meja Finance, Keuangan, Pajak, Pesanan (lihat)",
     "Kwitansi & alokasi, faktur pajak, selisih bayar, denda, setujui bayar sample, nilai kompensasi retur", "Membuat/konfirmasi SO · keputusan pemenuhan", "OK"),
    ("J05", "Gudang", "Meja Saya, Operasi Gudang (Barang Masuk/Keluar/Stok)",
     "Pick, potong, verifikasi label, loading check, kirim, hitung fisik penerimaan, potong sample", "Review GRN (403) · keputusan SPK · **scan retur (403 — F-11)**", "BUG F-11"),
    ("J06", "Admin Gudang", "Meja Gudang, Barang Masuk, Pengiriman, QC & Inspeksi",
     "Buat pengiriman, review & tutup GRN, tugaskan & putus SPK, pengecualian loading check, setujui opname/transfer", "Konfirmasi SO · harga", "OK"),
    ("J07", "Sopir", "Pengiriman (kiriman hari ini)", "Foto muat, berangkat, posisi, POD", "Melihat kode pickup · mengubah kiriman orang lain", ""),
    ("J08", "QC", "QC & Inspeksi", "SPK QC pesanan/random, 4-point, keputusan karantina kedatangan", "Menutup SPK (inspection.decide) · **QC retur (403 — F-11)**", "BUG F-11"),
    ("J09", "MD Quality", "QC & Inspeksi (Dokumen Inspeksi)", "Warna/labdip & handfeel, lepas/tolak tahanan, catat cutloss", "Menutup SPK", "INFO F-13"),
    ("J10", "MD / R&D", "Meja MD, R&D, Desainer, Produk & Harga, PR (lihat)", "Tugaskan desain, permintaan sample & penilaian, buat SKU, harga internal", "Membuat PO (403)", "OK 403"),
    ("J11", "Desainer", "Desainer › Permintaan Desain, Desain & Pattern", "Ambil tugas, unggah artwork, print paper, serahkan", "Menu pesanan, stok, uang · KPI desainer lain", ""),
    ("J12", "Admin Sample", "Meja Sample, Pesanan Sample", "Setujui bayar, teruskan ke gudang, terima hasil potong", "Pesanan roll biasa", "OK"),
    ("J13", "Role kustom & view-only", "Sesuai izin efektif", "Fungsi sama dengan peran acuan bila izin sama", "Aksi mutasi pada view-only; tautan langsung ke data di luar izin", ""),
]

CONSIST = [
    ("K01", "Meja vs daftar vs detail", "Jumlah per antrean (mis. *Perlu diverifikasi*, *Siap cetak*) = jumlah di daftar dengan filter sama; klik baris membuka dokumen yang benar.", ""),
    ("K02", "Perjalanan Pesanan", "Langkah Dipesan → Diverifikasi → Disetujui → Dikonfirmasi → Disiapkan → Dikirim → Diterima → Ditagih → Dibayar sesuai status nyata, dengan waktu & pelaku.", "BUG F-07"),
    ("K03", "Qty & nilai berantai", "SO (qty, harga, PPN) = Σ roll dialokasikan = Σ SJ = DPP/PPN faktur pajak = Σ kwitansi.", "OK SO-00038"),
    ("K04", "Satuan", "Yard dan kg tidak pernah dijumlah sebagai satu angka; QC selalu yard, stok knit tetap kg.", "BUG F-04"),
    ("K05", "Pesanan Khusus → SO", "Item A & B (SKU, unit, harga terkunci) sama di OD dan SO hasil konversi.", ""),
    ("K06", "Sample", "Nilai SOS = panjang potong aktual × harga sample; induk berkurang sama.", "GAP F-15"),
    ("K07", "Retur", "Qty klaim ≤ terkirim; hasil QC per roll = dasar kompensasi; saldo/refund/pengurangan tagihan sesuai keputusan.", ""),
    ("K08", "Laporan & Pusat Export", "Laporan penjualan & rapor desainer periode yang sama dapat ditelusuri ke dokumen; preview = unduhan = sumber; kolom di luar izin (grade, harga pokok) tidak ikut.", "BUG F-03 (grade)"),
    ("K09", "Ketahanan layar", "Refresh, klik ganda, kirim ulang, ganti SO cepat: tidak ada dokumen/stock movement ganda; galat terlihat; input tidak hilang.", "OK idempoten dispatch, faktur, kwitansi"),
]

TESTS = [
    ("Penjualan normal sampai lunas", "SO-00038 150 yd → verifikasi → ACC otomatis → konfirmasi → potong RL-36312 → anak RL-36312-1 → pick → cek muat (pengecualian) → SJ-00005 + SJ-00006 → LG-00001 armada + LG-00002 ekspedisi → POD → tandai diterima → FKT-00001 → AR-00003 (50%) + AR-00005 → Lunas", "Lulus dengan catatan F-05, F-06, F-07"),
    ("Harga khusus", "SO-00039: tolak → ajukan ulang → setujui → SO tetap terkunci; Edit/Override tidak membuka · SO-00040: Ganti Roll setelah diajukan → keputusan lama ditolak sistem", "Gagal F-09 · Lulus B07"),
    ("Kredit over-limit", "KANDA/SO-00007 Rp28,7 jt > limit Rp25 jt → entri kredit + hold → manajer setujui → SO Disetujui otomatis", "Lulus"),
    ("Termin CBD", "SO-00041 CBD → dikirim (SJ-00007) tanpa pembayaran", "Gagal F-10"),
    ("Ambil di gudang", "SO-00042 → tugas ditahan → pick ditolak → rilis → SJ-00008 → LG-00003 kode salah ditolak → serah terima", "Lulus"),
    ("QC sebelum kirim", "SO-00043 QC seluruh roll → kirim ditolak sebelum SPK QC selesai", "Lulus"),
    ("Stok kurang → pengadaan → QC", "SO-00045 100 kg → rencana 60 CST (KSC/IC-00009) + 40 PR-00042 → KSC/PO-00028 → KSC/GRN-00001 (fisik 38,5 vs SJ 40 kg, selisih diputus) → KSC/INS-00019 → karantina → 38,5 kg dicadangkan otomatis", "Lulus dengan catatan F-14"),
    ("Sample berbayar", "KSC/SOS-00002 → Setujui Bayar (Finance) → teruskan → potong 3,1 yd (RL-36312-2) → Admin Cutting → SJ-00009", "Lulus dengan catatan F-15"),
    ("Satu armada beberapa SO", "KSC/LG-00004 berisi SO-00041 + SOS-00002", "Lulus"),
    ("Retur pelanggan", "SRET-00006: 50 yd → izin manajer → terima Jakarta → kirim → tiba Rancamalang → QC 48 yd grade B → saldo kredit · SRET-00007: QC selesai tanpa barang diterima", "Lulus dengan F-11 · Gagal F-12"),
    ("Hak akses (negatif)", "Sales: approve SO/harga, tandai diterima, setujui retur, setujui bayar sample → 403 · MD buat PO → 403 · Admin Sales putus retur → 403", "Lulus"),
    ("Login & visibilitas", "Tombol login cepat per peran; respons API katalog untuk akun Sales", "Gagal F-01, F-03"),
    ("Uji ulang di kode terbaru", "21 Okt 03.05 pada main @ a3f7936 + perubahan lokal sesi lain: F-01 (login 401), F-02, F-03 (variant_label *Impor · 01 · A*), F-05 (SO-00085 alokasi tetap RL-36313 induk), F-06 & F-10 (SO-00084 CBD terkirim SJ-00012, POD → SO tetap Dikirim), F-07, F-09 (SO-00083), F-11 (403), F-12 (SRET-00020), F-16 — **semua masih terulang**. F-04, F-08, F-13, F-14, F-15, F-17 belum diuji ulang.", "11 temuan terkonfirmasi ulang"),
    ("Belum diuji pra-UAT", "Pesanan Khusus (modul berubah selama penyusunan), desain & R&D, makloon, transit Jakarta, pesanan pengganti retur, disposisi CST/supplier, denda, void kwitansi, role kustom, laporan & Pusat Export", "Wajib diuji peserta"),
]

# (id, prio, alur, temuan, dampak, akar masalah, rencana, uji, keputusan)
FINDINGS = [
    ("F-09", "P1", "B06, B15", "Entri persetujuan yang **ditolak** mengunci SO selamanya: setelah Sales mengajukan ulang dan manajer menyetujui, *Approve* tetap 409 *APPROVAL_REJECTED*; Edit/Override & ajukan ulang tidak membuka. (SO-00039)",
     "Nego ulang harga/kredit — kejadian harian — buntu; SO harus dibatalkan & dibuat ulang.",
     "`so_approvals.summarize()` menghitung semua entri *rejected*; `attach_order_price` hanya men-*supersede* entri *pending*.",
     "Saat pengajuan baru untuk tipe (+produk) yang sama dibuat, tandai entri *rejected* sebelumnya *superseded*; ringkasan hanya menilai entri terbaru per tipe/produk. Perbaiki juga pesan 409 *submit-for-approval* yang membingungkan.",
     "Tolak → ajukan ulang → setujui → SO Disetujui; tolak tanpa ajukan ulang tetap memblokir (regresi KN-D02).", "—"),
    ("F-10", "P1", "A17, I02", "Termin **CBD — Bayar Sebelum Kirim** (dan DP) tidak menahan pengiriman: SO-00041 dikirim (SJ-00007) dengan status bayar *pending*.",
     "Barang keluar tanpa uang; termin hanya label.", "`shipment_service.dispatch_task` & `loading_check_service.dispatch_guard` tidak memeriksa termin; `dp_percent` termin tidak dibaca saat kirim.",
     "Gerbang kirim: CBD → lunas; DP → terbayar ≥ dp_percent; pengecualian hanya peran berizin + alasan (teraudit). Tampilkan alasan di Barang Keluar & Meja Gudang.",
     "CBD belum bayar → 409; setelah kwitansi → kirim OK; DP 49% → 409; 50% → OK.", "Ya: blok keras atau peringatan? DP minimal?"),
    ("F-11", "P1", "H05–H08", "Peran **Gudang** dan **QC** tidak punya izin `sales_return`; scan terima/kirim/tiba retur & QC retur ditolak 403. Hanya Sales/Admin Sales/Manajer yang bisa.",
     "Alur fisik retur tidak bisa dijalankan oleh pelaku sebenarnya.", "`permissions_config.py` (warehouse/qc tanpa sales_return); `sales_returns.py` journey/scan & inspect/* memakai `sales_return.update` saja.",
     "Izinkan `wms.scan` untuk scan perjalanan retur dan `qc.inspect` untuk QC retur (pola `require_any_permission`, seperti keputusan 2026-10-21).",
     "Gudang scan TRM/SJ/TBA OK; QC mulai & selesai inspeksi OK; peran lain tetap ditolak.", "—"),
    ("F-12", "P1", "H08", "QC retur bisa **dimulai dan diselesaikan tanpa barang pernah di-scan terima** (SRET-00007). Pagar hanya aktif bila sebagian roll sudah di-scan.",
     "Keputusan kompensasi bisa didasarkan QC atas barang yang belum ada.", "`return_journey_service.assert_ready_for_qc` keluar dini bila `roll_locations` kosong; `start_inspection` tidak memeriksa penerimaan.",
     "Wajibkan semua roll klaim berstatus *diterima/tiba* sebelum mulai & selesai QC (kecuali jalur diskon foto KLR-06 yang tidak memakai QC fisik).",
     "Tanpa scan → 400; sebagian di perjalanan → 400; semua tiba → OK; jalur diskon foto tetap bisa.", "—"),
    ("F-05", "P1", "A13–A14", "Setelah reservasi potong dikonfirmasi (RL-36312 → anak RL-36312-1), **alokasi SO tetap menunjuk roll induk**. Pick mengikuti daftar → ditolak; harus memindai roll anak secara manual; SO terkirim dua SJ.",
     "Petugas gudang tersesat; risiko salah ambil & kirim parsial tak perlu.", "`roll_service.confirm_cut` membuat roll anak & memindah reservasi, tetapi tidak memperbarui `sales_orders.allocations[].rolls`.",
     "Saat potong dikonfirmasi, ganti entri roll induk di alokasi SO dengan roll anak (id, nomor, panjang aktual); picking list & Ganti Roll membaca data baru.",
     "Potong → alokasi menampilkan roll anak; pick dari daftar OK; satu SJ untuk qty penuh.", "—"),
    ("F-03", "P1", "A03, K08", "**Grade & LOT bocor ke Sales** lewat API: `GET /api/products` & `/sales-orders/frequent-products` mengirim `variant_label` *Lokal · TAUPE · A* / *Impor · 1 · A · LOT A*. Dipakai langsung di form harga khusus versi HP.",
     "Melanggar aturan owner *grade tidak boleh terlihat Sales, termasuk trial/API/export*.", "`field_visibility.py` menyamarkan SKU & nama, tetapi tidak `variant_label`.",
     "Saring segmen grade/LOT/asal pada `variant_label` (dan kunci serupa) sesuai `field_visibility`; tambah uji kebocoran ke sweep izin.",
     "Akun Sales: tidak ada grade/LOT di respons katalog, frequent-products, export; Admin tetap melihat.", "—"),
    ("F-01", "P1*", "Persiapan, J", "Tombol login cepat **Manajer/Admin Sales/Finance/Sales/Gudang** mengirim sandi `demo12345`, sedangkan akun peran di data acuan memakai `demo1234` → semua gagal kecuali Admin. Dokumentasi juga menyebut `demo12345`.",
     "Kesiapan UAT: peserta tidak bisa masuk dengan akun perannya.", "`LoginScreen.jsx:34` vs `backend/scripts/demo_api.py:12` (`DEMO_PASSWORD`).",
     "Samakan satu sandi demo (seed & tombol) atau sandi UAT dibagikan terpisah; perbarui AGENTS.md/LOCAL_DEV.md.",
     "Semua tombol peran berhasil masuk pada data acuan baru.", "—"),
    ("F-06", "P2", "A21–A23", "POD **Terkirim** + **Selesai** di Pengiriman tidak mengubah SO; SO tetap *Dikirim* sampai Admin Sales *Tandai diterima*.",
     "Dua pencatatan untuk satu kejadian; status bisa berbeda.", "`logistics_service.transition('delivered')` tidak memanggil penandaan SO diterima.",
     "Bila semua SJ SO sudah POD → tandai SO diterima otomatis (atau tampilkan tugas *konfirmasi diterima* di Meja Admin Sales).", "Semua SJ POD → SO Selesai / tugas muncul.", "Ya: otomatis atau manual?"),
    ("F-14", "P2", "D18–D19", "Barang datang: SPK inspeksi ditutup **terima**, roll tetap **karantina** sampai QC membuat **keputusan karantina** kedua di antrean.",
     "Dua keputusan untuk barang yang sama; barang bisa tertahan tanpa disadari.", "`inspection_service.finish` tidak melepas karantina; `qc-decision` terpisah.",
     "Satukan: keputusan SPK *terima* melepas karantina (atau antrean karantina menampilkan SPK terkait & keputusan cukup sekali).", "Tutup SPK terima → roll tersedia; tolak → tetap ditahan.", "Ya: satu atau dua keputusan?"),
    ("F-15", "P2", "E03–E08", "Sample berbayar: *Setujui Bayar* diberikan pada Rp83.250 (3 yd); setelah potong aktual 3,1 yd nilai menjadi Rp86.025 tanpa persetujuan ulang; status bayar tetap *pending*.",
     "Nilai disetujui ≠ nilai ditagih.", "`sample_orders.approve_payment` hanya flag; potong aktual menghitung ulang harga sesudahnya.",
     "Tetapkan aturan: toleransi selisih, persetujuan ulang bila melebihi, dan hubungkan dengan kwitansi.", "Selisih > toleransi → minta persetujuan ulang.", "Ya: toleransi & siapa memutus"),
    ("F-16", "P2", "I05", "Jatuh tempo dihitung dari **tanggal SO** (+ termin); SO yang belum dikirim/masih backorder/masih menunggu ACC (SO-00039, SO-00045) muncul *jatuh tempo 30 hari lagi*; SO termin **CBD** (SO-00084) juga tampil *30 hari lagi*.",
     "Penagihan dini & angka umur piutang salah.", "`customer_service.collection_reminders`: `due = created_at + term_days`.",
     "Hitung dari tanggal pengiriman pertama/tagihan (sejalan GL-03 pengakuan saat awal pengiriman); kecualikan SO belum dikirim.", "SO belum kirim tidak muncul; SO kirim tgl X → jatuh tempo X + termin.", "Konfirmasi dasar tanggal"),
    ("F-07", "P3", "K02", "Perjalanan Pesanan SO selesai menampilkan *Disiapkan gudang 0/1* (77,8%); langkah Disetujui/Dikonfirmasi tanpa waktu & pelaku.",
     "Pemantauan menyesatkan.", "`order_journey_service.py:173` tidak menghitung status *dispatched*; transisi tidak menulis approved_at/confirmed_at.",
     "Hitung *dispatched/partially_shipped* sebagai selesai disiapkan; stempel waktu & pelaku di transisi.", "SO selesai → 100%.", "—"),
    ("F-02", "P3", "A03", "Produk yang ditambah dari strip *Sering dibeli / Produk Terlaris* tampil **0 roll tersedia** di checkout walau ada 660 roll.",
     "Sales mengira stok kosong.", "`frequent-products` tidak mengirim `roll_count`; `CheckoutItemCard.jsx:25` membaca field itu.", "Lengkapi `roll_count`/ketersediaan dengan helper katalog.", "Angka roll sama dengan katalog.", "—"),
    ("F-04", "P3", "A03, K04", "Kartu POS **Jml Tersedia 1.375.897,08** / **Jml Dipesan** menjumlah yard + kg + meter tanpa satuan.", "Angka tidak bermakna.",
     "`App.js:502–503` memakai `metrics.available_qty` gabungan.", "Pecah per satuan atau ganti dengan jumlah roll/varian.", "Tidak ada penjumlahan lintas satuan.", "—"),
    ("F-08", "P3", "I04, K02", "Daftar *invoice* SO kosong setelah lunas lewat kwitansi (invoice hanya dari jalur simulasi lama); langkah *Ditagih* di Perjalanan = Faktur Pajak.",
     "Tidak jelas dokumen tagihan resmi untuk pelanggan non-PKP.", "`invoices.py` (simulate-payment) vs kwitansi AR; `order_journey_service`.",
     "Tetapkan Faktur Komersial (PDF) sebagai dokumen tagihan & tampilkan di SO/Perjalanan.", "Dokumen tagihan muncul per SO.", "Ya: dokumen tagihan resmi"),
    ("F-17", "P3", "Meja Admin Sales", "Antrean *Retur menunggu proses dokumen* menampilkan nilai **Rp0**.", "Prioritas kerja tidak terlihat.",
     "`work_desk_service` antrean retur tanpa nilai.", "Isi nilai = qty klaim × harga transaksi.", "Nilai sesuai klaim.", "—"),
    ("F-13", "Info", "D16", "MD Quality dapat mengisi hasil warna/handfeel saat SPK masih *Draf (belum ditugaskan)*; bagian QC ditolak pada status yang sama.",
     "Konsistensi gerbang SPK.", "`inspection_service.py:803` sengaja mengizinkan draf untuk bagian md_quality.", "Konfirmasi maksud desain; bila tidak dimaksud, wajibkan SPK ditugaskan.", "—", "Ya: konfirmasi"),
]


def access_page():
    rows = "".join(f"<tr><td class='no'>{a}</td><td>{role_cell(b)}</td><td>{fmt(c)}</td><td>{fmt(d)}</td><td class='dec'>{fmt(e)}</td>"
                   f"<td>{_t(f)}</td></tr>" for a, b, c, d, e, f in ACCESS)
    krows = "".join(f"<tr><td class='no'>{a}</td><td><b>{escape(b)}</b></td><td>{fmt(c)}</td><td>{_t(d)}</td></tr>" for a, b, c, d in CONSIST)
    return f"""<section class="sec">{head("Alur J & K", "J — Akses per peran · K — Konsistensi data & laporan", ["Hari 1 08.30 & Hari 2 15.00"])}
<table class="grid"><colgroup><col style="width:5%"><col style="width:12%"><col style="width:21%"><col style="width:26%"><col style="width:24%"><col style="width:12%"></colgroup>
<thead><tr><th>ID</th><th>Peran · akun</th><th>Pintu kerja (menu)</th><th>Boleh — uji positif</th><th>Tidak boleh — uji negatif (harus ditolak)</th><th>Uji pra-UAT</th></tr></thead><tbody>{rows}</tbody></table>
<h3>K — Konsistensi data</h3>
<table class="grid"><colgroup><col style="width:5%"><col style="width:17%"><col style="width:64%"><col style="width:14%"></colgroup>
<thead><tr><th>ID</th><th>Pemeriksaan</th><th>Harus benar</th><th>Uji pra-UAT</th></tr></thead><tbody>{krows}</tbody></table></section>"""


def _t(t):
    from page import test_cell
    return test_cell(t)


def tests_page():
    rows = "".join(f"<tr><td><b>{escape(a)}</b></td><td>{fmt(b)}</td><td>{_res(c)}</td></tr>" for a, b, c in TESTS)
    return f"""<section class="sec">{head("Uji pra-UAT", "Hasil uji tim IT sebelum UAT (21 Oktober 2026)", ["Data acuan lokal", "Kandidat af24f9c + FE-01 lokal", "API + layar"])}
<p class="lead">Tim IT menjalankan alur nyata memakai akun per peran (bukan Admin) lewat API aplikasi dan layar POS/Meja. Nomor dokumen di bawah ada di
basis data acuan lokal dan dapat dibuka untuk diperiksa. Ini <b>bukan</b> pengganti UAT: peserta tetap menjalankan setiap langkah di layar.</p>
<table class="grid"><colgroup><col style="width:17%"><col style="width:63%"><col style="width:20%"></colgroup>
<thead><tr><th>Area</th><th>Skenario yang dijalankan & dokumen bukti</th><th>Hasil</th></tr></thead><tbody>{rows}</tbody></table>
<div class="strip c3">
<div class="box g"><b class="t">Terbukti berfungsi</b><ul><li>Urutan verifikasi → ACC → konfirmasi ditegakkan server</li><li>Bukti wajib pengiriman (foto muat, resi, POD, kode pickup)</li><li>Penerimaan memakai qty fisik; selisih wajib diputus</li><li>Rencana pemenuhan multi-sumber & retry aman</li></ul></div>
<div class="box r"><b class="t">Gagal (Prioritas 1)</b><ul><li>F-09 SO terkunci setelah penolakan</li><li>F-10 CBD/DP tidak menahan kirim</li><li>F-11 Gudang/QC tak bisa memproses retur</li><li>F-12 QC retur tanpa barang diterima</li><li>F-05 alokasi tak ikut roll anak · F-03 grade bocor · F-01 login peran</li></ul></div>
<div class="box a"><b class="t">Perlu keputusan owner</b><ul><li>F-06 POD menutup SO otomatis?</li><li>F-10 CBD/DP: blok keras atau peringatan?</li><li>F-14 satu atau dua keputusan QC kedatangan</li><li>F-15 toleransi nilai sample · F-16 dasar jatuh tempo</li></ul></div>
</div></section>"""


def _res(c):
    cls = "t-ok" if c.startswith("Lulus") and "Gagal" not in c else ("t-bad" if "Gagal" in c else "t-warn")
    return f'<span class="{cls}">{escape(c)}</span>'


def findings_pages():
    rows = []
    for fid, pr, alur, tem, dmp, akar, ren, uji, kep in FINDINGS:
        sev = {"P1": "P1", "P1*": "P1", "P2": "P2", "P3": "P3"}.get(pr, "P3")
        rows.append(f"<tr><td class='no'>{fid}<br><span class='sev {sev}'>{escape(pr)}</span></td><td>{escape(alur)}</td><td>{fmt(tem)}</td>"
                    f"<td>{fmt(dmp)}</td><td class='small'>{fmt(akar)}</td><td>{fmt(ren)}</td><td class='small'>{fmt(uji)}</td><td class='dec'>{fmt(kep)}</td></tr>")
    table = ("<table class='grid'><colgroup><col style='width:5.5%'><col style='width:6%'><col style='width:21%'><col style='width:11%'>"
             "<col style='width:15%'><col style='width:18%'><col style='width:14%'><col style='width:9.5%'></colgroup>"
             "<thead><tr><th>ID</th><th>Langkah</th><th>Temuan (cara reproduksi)</th><th>Dampak UAT</th><th>Akar masalah</th>"
             "<th>Rencana perbaikan</th><th>Uji regresi</th><th>Keputusan owner?</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>")
    return f"""<section class="sec">{head("Temuan", "17 temuan dari uji pra-UAT — akar masalah & rencana perbaikan", ["P1 = blok alur / aturan owner", "P2 = celah proses", "P3 = tampilan / kejelasan"])}
<p class="lead">Ditemukan 21 Okt 02.00–02.45 (main @ af24f9c); <b>uji ulang 03.05 pada main @ a3f7936 + perubahan lokal</b>: F-01, F-02, F-03, F-05, F-06, F-07, F-09, F-10, F-11, F-12, F-16 masih terulang. P1* = blok kesiapan UAT (bukan logika bisnis). Kolom akar masalah menunjuk berkas kode; detail teknis & urutan kerja ada di
<b>RENCANA_PERBAIKAN_TEMUAN_UAT.md</b> (berkas pendamping).</p>{table}</section>"""


PLAN = [
    ("Gelombang 1 — wajib sebelum UAT (H-3)", "r", [
        "**F-09** persetujuan ditolak mengunci SO (backend so_approvals + router) · S–M",
        "**F-11** izin Gudang/QC untuk perjalanan & QC retur · S",
        "**F-12** QC retur wajib setelah barang diterima · S",
        "**F-05** alokasi SO ikut roll anak setelah potong · M",
        "**F-03** saring grade/LOT pada variant_label untuk POV Sales · S–M",
        "**F-01** samakan sandi demo / bagikan sandi UAT · XS",
        "**F-10** gerbang kirim CBD/DP — setelah owner memilih blok keras/peringatan · M"]),
    ("Gelombang 2 — setelah keputusan owner", "a", [
        "**F-06** POD → SO diterima (otomatis atau tugas konfirmasi) · S",
        "**F-14** satukan keputusan SPK & karantina kedatangan · M",
        "**F-15** aturan nilai sample berbayar setelah potong aktual · S",
        "**F-16** dasar tanggal jatuh tempo dari pengiriman/tagihan · S",
        "**F-08** dokumen tagihan resmi (Faktur Komersial) di SO & Perjalanan · S"]),
    ("Gelombang 3 — kejelasan layar", "", [
        "**F-07** Perjalanan Pesanan (status dispatched, waktu & pelaku) · XS",
        "**F-02** roll_count di strip Sering dibeli · XS",
        "**F-04** KPI POS per satuan · XS",
        "**F-17** nilai antrean retur · XS",
        "**F-13** konfirmasi desain gerbang MD Quality"]),
    ("Cara kerja & verifikasi", "g", [
        "Ikuti protokol `docs/reviews/README.md`: tiap perbaikan = tes merah-dulu + commit + laporan `hasil/`.",
        "Status maksimal implementer: *implemented_pending_review*; validasi oleh reviewer.",
        "Setelah Gelombang 1: ulangi skenario pra-UAT terkait (SO-00039, SO-00041, SRET-00007, potong roll, login peran).",
        "Jangan mengubah file Pesanan Khusus selama sesi FE-01 masih berjalan."]),
]


def plan_page():
    cols = "".join(f'<div class="box {k}"><b class="t">{escape(t)}</b><ul>' + "".join(f"<li>{fmt(x)}</li>" for x in items) + "</ul></div>"
                   for t, k, items in PLAN)
    pend = [
        ("DES-02", "Penamaan & pengelompokan dokumen per leg (SJ transit vs SJ pelanggan, manifest induk)", "G05–G07", "Owner / IT"),
        ("DATA-01", "Dataset master bahan, supplier & warna yang final", "D, F", "Owner"),
        ("DES-03", "Format rapor & kamus metrik (rapor desainer, laporan)", "K08", "Owner"),
        ("DES-04", "Konteks multi-entitas workspace MD", "F, D", "Owner"),
        ("HW-01/02", "Perangkat RFID & absensi aktual (uji fisik)", "A16, G03", "Owner / vendor"),
        ("UAT-01", "Lingkungan pilot & persetujuan akhir", "Semua", "Owner"),
        ("Q-01 (F-06)", "POD pengiriman menutup SO otomatis atau tetap manual?", "A23", "Owner"),
        ("Q-02 (F-10)", "CBD/DP: blok keras kirim atau peringatan? DP minimal sebelum kirim?", "A17, I02", "Owner + Finance"),
        ("Q-03 (F-14)", "Barang datang: cukup satu keputusan (SPK) atau tetap dua?", "D18–D19", "Owner + MD Quality"),
        ("Q-04 (F-15)", "Sample berbayar: toleransi selisih panjang aktual & persetujuan ulang", "E03–E08", "Owner + Finance"),
        ("Q-05 (F-16)", "Jatuh tempo dihitung dari SJ pertama / faktur?", "I05", "Finance"),
        ("Q-06 (F-13)", "MD Quality boleh mengisi sebelum SPK ditugaskan?", "D16", "Owner"),
    ]
    prow = "".join(f"<tr><td class='no'>{escape(a)}</td><td>{escape(b)}</td><td>{escape(c)}</td><td>{escape(d)}</td></tr>" for a, b, c, d in pend)
    return f"""<section class="sec">{head("Rencana perbaikan", "Rencana perbaikan bertahap & keputusan yang masih ditunggu", ["XS < ½ hari · S ≈ 1 hari · M ≈ 2–3 hari"])}
<div class="strip">{cols}</div>
<h3>Keputusan bisnis yang belum diputus — jangan diasumsikan saat UAT (catat <i>Terblokir</i>)</h3>
<table class="grid"><colgroup><col style="width:11%"><col style="width:59%"><col style="width:15%"><col style="width:15%"></colgroup>
<thead><tr><th>Kode</th><th>Pertanyaan</th><th>Langkah terdampak</th><th>Pemutus</th></tr></thead><tbody>{prow}</tbody></table>
<p class="small" style="margin-top:2mm">Sudah diputus owner (19 Okt) dan dipakai di dokumen ini: KLR-01…11 (cutloss, kompensasi, tukar, diskon foto, hangtag, batas 21 hari, pengurangan tagihan, ongkir), KLX-01…03, CUT-01…05, GL-01…08, OPS-01.</p></section>"""


def result_sheet(groups):
    body = []
    for title, rows in groups:
        body.append(f"<tr><td colspan='6' style='background:#E2E8F0;font-weight:700'>{escape(title)}</td></tr>")
        for no, act in rows:
            body.append(f"<tr><td class='no'>{escape(no)}</td><td>{escape(_short(act))}</td>"
                        f"<td><span class='cb'></span>L <span class='cb'></span>G <span class='cb'></span>T <span class='cb'></span>TD</td>"
                        f"<td></td><td></td><td></td></tr>")
    return [f"""<section class="sec">{head("Lembar hasil", "Lembar hasil per langkah", ["L = Lulus · G = Gagal · T = Terblokir · TD = Tidak diuji"])}
<table class="grid steps"><colgroup><col style="width:6%"><col style="width:40%"><col style="width:17%"><col style="width:13%"><col style="width:18%"><col style="width:6%"></colgroup>
<thead><tr><th>Langkah</th><th>Ringkasan</th><th>Status</th><th>No. dokumen</th><th>Catatan / ID temuan</th><th>Paraf</th></tr></thead><tbody>{"".join(body)}</tbody></table></section>"""]


def _short(s, n=95):
    import re
    s = re.sub(r"\[\[|\]\]|\*\*|`|\*", "", s)
    return s if len(s) <= n else s[:n - 1].rsplit(" ", 1)[0] + " …"


def signoff():
    return f"""<section class="sec">{head("Penutupan", "Berita acara UAT", ["Diisi pada akhir Hari 2"])}
<table class="grid"><colgroup><col style="width:30%"><col style="width:70%"></colgroup><tbody>
<tr><td><b>Tanggal pelaksanaan</b></td><td>Hari 1: ____________ · Hari 2: ____________</td></tr>
<tr><td><b>Kandidat diuji</b></td><td>URL ____________ · commit ____________ · perubahan lokal ____________</td></tr>
<tr><td><b>Rekap status langkah</b></td><td>Lulus ____ · Gagal ____ · Terblokir ____ · Tidak diuji ____ · total ____</td></tr>
<tr><td><b>Alur dinyatakan siap pakai</b></td><td>☐ A ☐ B ☐ C ☐ D ☐ E ☐ F ☐ G ☐ H ☐ I ☐ J ☐ K</td></tr>
<tr><td><b>Temuan terbuka (ID & prioritas)</b></td><td style="height:16mm"></td></tr>
<tr><td><b>Keputusan bisnis yang diambil</b></td><td style="height:16mm"></td></tr>
<tr><td><b>Rencana perbaikan & tanggal uji ulang</b></td><td style="height:16mm"></td></tr>
</tbody></table>
<div class="sign"><div>Pemilik proses / client</div><div>Production IT</div><div>Fasilitator</div><div>Pencatat</div></div>
<h3>Form satu temuan (salin per temuan)</h3>
<table class="grid"><colgroup><col style="width:22%"><col style="width:28%"><col style="width:22%"><col style="width:28%"></colgroup><tbody>
<tr><td><b>ID temuan / langkah</b></td><td></td><td><b>Akun / peran / badan usaha</b></td><td></td></tr>
<tr><td><b>Dokumen / roll</b></td><td></td><td><b>Waktu kejadian</b></td><td></td></tr>
<tr><td><b>Langkah reproduksi</b></td><td colspan="3" style="height:12mm"></td></tr>
<tr><td><b>Seharusnya</b></td><td></td><td><b>Yang terjadi / dampak</b></td><td></td></tr>
<tr><td><b>Bug atau keputusan bisnis?</b></td><td>☐ bug ☐ keputusan ☐ data</td><td><b>Prioritas / PIC / target</b></td><td></td></tr>
</tbody></table></section>"""
