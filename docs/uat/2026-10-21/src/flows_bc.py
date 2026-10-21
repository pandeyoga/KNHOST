"""Alur B — gerbang persetujuan (harga khusus, kredit, nilai) · Alur C — stok kurang & pemenuhan."""
from diagram import Diagram

R, G = "#B91C1C", "#15803D"


def b1():
    d = Diagram(["sales", "sadm", "mgr", "sys"], 8, lane_h={"sales": 80, "sadm": 70, "mgr": 80, "sys": 74})
    d.n("b01", "sales", 0, "task", "Minta Harga Khusus: harga, alasan, bukti", "B01")
    d.n("b02", "sys", 1, "auto", "Entri harga khusus pending + versi alokasi", "B02")
    d.n("b03", "sadm", 2, "task", "Verifikasi → Ajukan persetujuan", "B03")
    d.n("b04", "mgr", 3, "gate", "Manajer: putuskan harga khusus", "B04")
    d.n("dk", "mgr", 4, "decision", "Keputusan?")
    d.n("b06", "sales", 4, "task", "Ajukan ulang harga baru / batalkan SO", "B06")
    d.n("b07", "sadm", 4, "task", "Ganti roll / qty sesudah diajukan", "B07")
    d.n("b05", "sys", 5, "auto", "Harga baris diganti · total & PPN dihitung ulang", "B05")
    d.n("da", "sys", 6, "decision", "Semua gerbang ACC?")
    d.n("ok", "sadm", 7, "task", "SO Disetujui → Konfirmasi (A11)")
    d.n("lA3", "mgr", 7, "link", "A3")
    d.e("b01", "b02", fs_="b", ts="l", via=[(d.nodes["b01"]["cx"], d.nodes["b02"]["cy"])])
    d.e("b02", "b03", fs_="t", ts="l", via=[(d.nodes["b02"]["cx"], d.nodes["b03"]["cy"])])
    d.e("b03", "b04", fs_="r", ts="t", via=[(d.nodes["b04"]["cx"], d.nodes["b03"]["cy"])])
    d.e("b04", "dk")
    d.e("dk", "b05", "setuju", fs_="b", ts="l", via=[(d.nodes["dk"]["cx"], d.nodes["b05"]["cy"])], color=G)
    d.e("dk", "b06", "tolak", fs_="r", ts="r", via=[(d.nodes["dk"]["cx"] + 70, d.nodes["dk"]["cy"]), (d.nodes["dk"]["cx"] + 70, d.nodes["b06"]["cy"])], color=R)
    d.e("b06", "b02", "pengajuan baru", fs_="l", ts="t", via=[(d.nodes["b02"]["cx"], d.nodes["b06"]["cy"])], style="dash", color=R)
    d.e("b07", "b06", "keputusan lama ditolak sistem", fs_="t", ts="b", style="dash", color=R)
    d.e("b05", "da")
    d.e("da", "ok", "ya", fs_="t", ts="b", via=[(d.nodes["da"]["cx"], d.nodes["ok"]["cy"] + 60), (d.nodes["ok"]["cx"], d.nodes["ok"]["cy"] + 60)], color=G)
    d.e("ok", "lA3", fs_="b", ts="t")
    d.e("da", "b04", "masih ada gerbang lain", fs_="b", ts="b", via=[(d.nodes["da"]["cx"], d.height - 5), (d.nodes["b04"]["cx"], d.height - 5)], style="dash")
    return d


B1_ROWS = [
    ("B01", "Sales", "Sebelum SO: `Checkout › Termin & Lot` → kartu item → [[Minta Harga Khusus]]\nSesudah SO (tahap Dipesan): `Pesanan (SO) › detail › Persetujuan` → ajukan harga khusus",
     "Isi harga per satuan yang diminta, qty minimum (opsional), **alasan (wajib)**, lampirkan bukti persetujuan atasan / percakapan pelanggan.",
     "Harga tetap untuk pelanggan (bukan per pesanan) → `Produk & Harga › Harga per Pelanggan` (admin/manajer), bukan jalur ini.",
     "Entri **Approval Harga Khusus** berstatus *pending*; SO sub-status *Menunggu approval harga khusus*; muncul di `Pusat Persetujuan › Pengajuan Harga Khusus`.",
     "OK alasan kosong ditolak; pengajuan tercatat (SO-00039)"),
    ("B02", "Sistem", "otomatis",
     "Menyimpan harga normal vs diminta + **versi alokasi** (roll & qty saat diajukan). Pengajuan baru untuk produk yang sama menggantikan yang masih pending (*superseded*).",
     "—", "Riwayat semua pengajuan tetap terlihat.", "OK"),
    ("B03", "Admin Sales", "`Meja Admin Sales` → **Perlu diverifikasi** → [[Verifikasi]] → [[Ajukan persetujuan]]",
     "Verifikasi kelengkapan (A08) lalu ajukan. Admin Sales hanya memantau antrean **Menunggu keputusan manajer**.",
     "—", "SO *Menunggu persetujuan* (*Menunggu approval harga*). Approve SO & konfirmasi ditolak selama harga pending.",
     "OK 409 APPROVAL_PENDING & konfirmasi ditolak"),
    ("B04", "Manajer", "`Meja Saya` → **Permintaan harga khusus** → [[Putuskan]]  /  `Pusat Persetujuan › Inbox Persetujuan`",
     "Bandingkan harga normal vs diminta, margin, alasan & bukti. Putuskan per entri [[Setujui]] / [[Tolak]] + catatan keputusan.",
     "Pengaju tidak boleh memutus pengajuannya sendiri. Sales tidak punya izin memutus (403).",
     "Pemutus, waktu & catatan tercatat pada entri dan dokumen harga khusus.", "OK 403 untuk Sales"),
    ("B05", "Sistem", "otomatis setelah **Setujui**",
     "Harga baris diganti harga khusus; subtotal, DPP, PPN, grand total dihitung ulang; sumber harga = *special_approval*.",
     "Bila **semua** entri persetujuan SO disetujui → SO otomatis **Disetujui** (roll dikunci).",
     "Contoh uji: 110 yd × Rp19.000 → Grand Total Rp2.319.900.", "OK harga & total"),
    ("B06", "Sales", "detail SO → ajukan harga khusus lagi, atau [[Batalkan]] SO",
     "Setelah ditolak: nego ulang dengan pelanggan → ajukan harga baru; atau batalkan pesanan.",
     "Pengajuan baru disetujui → SO **seharusnya** lanjut ke Disetujui.",
     "Entri lama tetap *ditolak* sebagai riwayat; entri baru *pending → approved*.",
     "BUG F-09 SO terkunci permanen (APPROVAL_REJECTED) walau pengajuan ulang disetujui; Edit/Override tidak membuka"),
    ("B07", "Admin Sales", "detail SO → [[Ganti Roll]] (*Ganti Roll — Alokasi Manual*) / [[Edit / Override SO]]",
     "Admin Sales menentukan alokasi roll, qty & harga final. Bila alokasi berubah setelah harga diajukan, ajukan ulang untuk versi alokasi terbaru.",
     "Manajer memutus pengajuan lama → sistem menolak: *Alokasi roll/qty baris ini berubah sejak harga diajukan…*",
     "Tidak ada harga khusus yang menempel pada alokasi yang sudah tidak berlaku.", "OK (SO-00040)"),
]


def b2():
    d = Diagram(["sales", "sadm", "mgr", "fin", "sys"], 8, lane_h={"sales": 74, "sadm": 66, "mgr": 74, "fin": 62, "sys": 74})
    d.n("b11", "sys", 0, "auto", "SO dibuat: cek limit, tunggakan, override", "B11")
    d.n("dc", "sys", 1, "decision", "Over-limit / tunggakan?")
    d.n("lA2", "sys", 2, "link", "A2")
    d.n("b12", "sales", 2, "task", "Checkout: lihat status kredit · minta persetujuan kredit", "B12")
    d.n("b13", "sadm", 3, "task", "Verifikasi (kredit = peringatan) → Ajukan", "B13")
    d.n("b14", "mgr", 4, "gate", "Putuskan kredit + bukti", "B14")
    d.n("dk", "mgr", 5, "decision", "Keputusan?")
    d.n("ok", "sys", 6, "auto", "Hold kredit dilepas · SO Disetujui", w=128)
    d.n("b15", "sales", 6, "task", "Opsi: DP / CBD, kurangi qty, lunasi tunggakan", "B15")
    d.n("b16", "fin", 6, "task", "Tunggakan dilunasi → limit pulih", "B16")
    d.n("lA3", "sys", 7, "link", "A3")
    d.e("b11", "dc")
    d.e("dc", "lA2", "tidak", color=G)
    d.e("dc", "b12", "ya", fs_="t", ts="l", via=[(d.nodes["dc"]["cx"], d.nodes["b12"]["cy"])], color=R)
    d.e("b12", "b13", fs_="b", ts="l", via=[(d.nodes["b12"]["cx"], d.nodes["b13"]["cy"])])
    d.e("b13", "b14", fs_="r", ts="t", via=[(d.nodes["b14"]["cx"], d.nodes["b13"]["cy"])])
    d.e("b14", "dk")
    d.e("dk", "ok", "setuju", fs_="b", ts="l", via=[(d.nodes["dk"]["cx"], d.nodes["ok"]["cy"])], color=G)
    d.e("dk", "b15", "tolak", fs_="t", ts="l", via=[(d.nodes["dk"]["cx"], d.nodes["b15"]["cy"])], color=R)
    d.e("b15", "b16", "lunasi", fs_="b", ts="t", style="dash")
    d.e("ok", "lA3")
    return d


B2_ROWS = [
    ("B11", "Sistem", "otomatis saat [[Buat Sales Order]]",
     "Menghitung eksposur pelanggan (piutang + SO terbuka) vs **limit kredit**, tunggakan lewat jatuh tempo, dan override kredit yang masih berlaku (sekali pakai).",
     "Tidak melanggar → lanjut A2. Melanggar → entri **Approval Kredit (Over-limit)** + *credit hold*.",
     "SO sub-status *Menunggu approval kredit*; dokumen *credit override* pending dibuat.", "OK KANDA/SO-00007 Rp28,7 jt > limit Rp25 jt"),
    ("B12", "Sales", "`Checkout › Review` (status kredit) · detail SO → minta persetujuan kredit",
     "Checkout menampilkan *Kredit OK* / *Peringatan kredit (mendekati limit / ada tunggakan)* / *Terblokir Kredit* / *Kredit terblokir, tapi ada Override disetujui*. Bila perlu, ajukan persetujuan kredit + alasan.",
     "Permintaan kedua saat masih ada yang pending → ditolak.", "Satu entri kredit pending per SO.", ""),
    ("B13", "Admin Sales", "`Meja Admin Sales` → [[Verifikasi]] → [[Ajukan persetujuan]]",
     "Checklist menampilkan *Tidak tertahan batas kredit* sebagai **peringatan** (keputusan kredit milik manajer).", "—",
     "SO *Menunggu persetujuan*; approve SO langsung ditolak selama kredit pending.", "OK 409 APPROVAL_PENDING"),
    ("B14", "Manajer", "`Pusat Persetujuan › Inbox Persetujuan` / `Meja Saya` → [[Putuskan]]",
     "Tinjau limit, eksposur, umur piutang; lampirkan bukti (mis. persetujuan direksi). [[Setujui]] / [[Tolak]] + catatan.", "—",
     "Setuju → *credit hold* dilepas, override tercatat terpakai, SO **Disetujui** otomatis.", "OK SO otomatis Approved"),
    ("B15", "Sales", "detail SO / pelanggan",
     "Bila ditolak: tawarkan DP/CBD, kurangi qty, atau tunggu pelunasan tunggakan; ajukan ulang.",
     "Pengajuan ulang setelah ditolak → **lihat F-09** (SO bisa terkunci).", "—", "BUG F-09 berlaku juga untuk entri kredit"),
    ("B16", "Finance", "`Meja Finance` → **Uang masuk** → [[Catat kwitansi]]",
     "Pelunasan tunggakan dicatat (Alur I) → limit tersedia kembali untuk SO berikutnya.", "—", "Eksposur pelanggan turun.", ""),
    ("B17", "Admin", "`Pengaturan › Aturan Persetujuan` (khusus admin)",
     "Ambang **nilai** SO (min/max → peran). Bawaan sekarang: tanpa ambang. Uji ambang sementara hanya bila disepakati (pengaturan global — jangan saat skenario lain berjalan).",
     "SO di atas ambang → entri *Approval Nilai Order*.", "Gerbang nilai muncul & diputus manajer.", "NA perlu jendela konfigurasi"),
    ("B18", "Sales", "`Checkout` (konfirmasi pakai stok cadangan makloon)",
     "Bila stok yang dipilih sedang dicadangkan untuk makloon, sistem meminta konfirmasi lalu membuat entri persetujuan *makloon*.", "Manajer memutus.", "SO tertahan sampai diputus.", ""),
]


def c1():
    d = Diagram(["sales", "sadm", "ptl", "pur", "sys"], 8, lane_h={"sales": 64, "sadm": 82, "ptl": 72, "pur": 66, "sys": 74})
    d.n("c01", "sales", 0, "task", "SO dengan izin backorder", "C01")
    d.n("c02", "sys", 1, "auto", "SO Menunggu stok · baris backorder", "C02")
    d.n("c03", "sadm", 2, "task", "Meja Admin Sales: Perlu dipenuhi → Atur pemenuhan", "C03")
    d.n("dp", "sadm", 3, "decision", "Bagi per sumber")
    d.n("c05", "ptl", 4, "task", "PIN → transaksi antar-PT (IC)", "C05")
    d.n("c06", "pur", 4, "task", "PR otomatis → PO (Alur D)", "C06")
    d.n("cw", "sys", 4, "auto", "Tunggu barang masuk (PO berjalan)")
    d.n("cs", "sadm", 4, "task", "Stok sendiri gudang lain", dy=0)
    d.n("c07", "ptl", 5, "task", "PT pemasok proses & serah barang", "C07")
    d.n("c08", "sys", 6, "auto", "Barang tersedia → dicadangkan ke SO (FIFO)", "C08", w=124)
    d.n("c09", "sadm", 7, "task", "Ajukan & Konfirmasi lagi", "C09")
    d.n("lA3", "sys", 7, "link", "A3")
    d.e("c01", "c02", fs_="b", ts="l", via=[(d.nodes["c01"]["cx"], d.nodes["c02"]["cy"])])
    d.e("c02", "c03", fs_="t", ts="l", via=[(d.nodes["c02"]["cx"], d.nodes["c03"]["cy"])])
    d.e("c03", "dp")
    d.e("dp", "cs", "sendiri", lx=None)
    d.e("dp", "c05", "PT lain", fs_="b", ts="l", via=[(d.nodes["dp"]["cx"], d.nodes["c05"]["cy"])])
    d.e("dp", "c06", "supplier", fs_="b", ts="l", via=[(d.nodes["dp"]["cx"] - 14, d.nodes["dp"]["cy"] + 27), (d.nodes["dp"]["cx"] - 14, d.nodes["c06"]["cy"])])
    d.e("dp", "cw", "tunggu", fs_="b", ts="l", via=[(d.nodes["dp"]["cx"] - 28, d.nodes["dp"]["cy"] + 20), (d.nodes["dp"]["cx"] - 28, d.nodes["cw"]["cy"])])
    d.e("c05", "c07")
    d.e("c07", "c08", fs_="r", ts="t", via=[(d.nodes["c08"]["cx"] - 30, d.nodes["c07"]["cy"]), (d.nodes["c08"]["cx"] - 30, d.nodes["c08"]["cy"] - 37)])
    d.e("c06", "c08", fs_="r", ts="l", via=[(d.nodes["c08"]["cx"] - 90, d.nodes["c06"]["cy"]), (d.nodes["c08"]["cx"] - 90, d.nodes["c08"]["cy"])])
    d.e("cw", "c08", fs_="r", ts="l")
    d.e("cs", "c09", fs_="r", ts="l", style="dash")
    d.e("c08", "c09", fs_="t", ts="b", via=[(d.nodes["c08"]["cx"] + 30, d.nodes["c08"]["cy"] - 37), (d.nodes["c08"]["cx"] + 30, d.nodes["c09"]["cy"] + 46), (d.nodes["c09"]["cx"], d.nodes["c09"]["cy"] + 46)], color=G)
    d.e("c09", "lA3", fs_="r", ts="t", via=[(d.nodes["lA3"]["cx"], d.nodes["c09"]["cy"])])
    return d


C1_ROWS = [
    ("C01", "Sales", "`Penjualan › POS` → checkout (izin backorder)",
     "Pesan artikel yang stok PT sendiri kurang (contoh uji: *ALICE KNIT 14 A*, stok hanya di CST, 100 kg).",
     "Tanpa izin backorder → ditolak *Stok milik entitas tidak mencukupi… Aktifkan backorder*.",
     "SO **Menunggu stok** (*Reserved · menunggu_stok*); pratinjau pemenuhan menunjukkan *Sebagian via backorder*.", "OK KSC/SO-00045"),
    ("C02", "Sistem", "otomatis",
     "Mencatat baris backorder per produk (qty kurang). SO muncul di **Keep & Pending** dan antrean **Perlu dipenuhi (kurang stok)**; Sales melihat *Pesanan saya menunggu* di Meja Saya.",
     "—", "Kekurangan tampil per produk & dokumen sumber; Sales tidak melihat pemilik stok.", "OK"),
    ("C03", "Admin Sales", "`Meja Admin Sales` → **Perlu dipenuhi (kurang stok)** → [[Putuskan pemenuhan]] · atau Pelacak SO → [[Atur pemenuhan]]",
     "Panel menampilkan stok sendiri per gudang, stok di PT lain + kesiapan harga internal, PO yang sedang berjalan, dan sisa kebutuhan.",
     "Verifikasi (A08) boleh dilakukan sebelum/selama menunggu stok.", "Opsi tidak layak diberi alasan (bukan tombol mati).", "OK"),
    ("C04", "Admin Sales", "panel **Rencana pemenuhan** → isi qty per sumber → simpan",
     "Bagi kekurangan per baris: **stok sendiri** (gudang lain) · **transfer dari PT lain** (boleh >1 PT) · **PO ke supplier** (lewat PR) · **tunggu barang masuk**; penuh atau sebagian; isi catatan.",
     "Total rencana > kekurangan → ditolak. Jalankan ulang → tidak menggandakan PR (qty tidak ditambah).",
     "Keputusan tercatat di SO (*Keputusan pemenuhan*), dokumen tertaut dua arah.", "OK 70+40>100 ditolak; 60 CST + 40 PO; retry aman"),
    ("C05", "Admin Sales", "otomatis dari rencana · `Pesanan › Permintaan Internal (PIN)`",
     "Jalur PT lain membuat **PIN** lalu **Transaksi Antar-PT** (dokumen kembar penjual-pembeli, contoh KSC/IC-00009). Harga internal wajib ada (`Produk & Harga › Harga Internal Antar-PT`).",
     "Harga internal belum ada → ditolak dan PIN dibatalkan otomatis.", "SO ⇄ transaksi antar-PT saling tertaut.", "OK IC-00009 terbentuk"),
    ("C06", "Pembelian", "otomatis → `Pembelian › Pengadaan › Permintaan Pembelian`",
     "Jalur supplier membuat **PR** dari SO (contoh PR-00042, 40 kg). Dilanjutkan di **Alur D** (PR → PO → kedatangan → QC).", "PR ≥ Rp50 jt → ACC manajer.",
     "PR merujuk SO asal.", "OK PR-00042"),
    ("C07", "CST", "`Akuntansi & Pajak › Antar Entitas (Grup)` / `Retur & transfer antar-PT` (PT pemasok)",
     "PT pemasok menyetujui & menyerahkan barang; pergantian pemilik lewat dokumen resmi. Bila beda lokasi: transfer fisik + penerimaan di gudang tujuan.",
     "Pemilik berubah **tidak berarti** barang sudah tiba.", "Owner & lokasi fisik dapat dibedakan; gudang tujuan menerima roll yang benar.", "NA serah terima CST belum diuji"),
    ("C08", "Sistem", "otomatis saat barang lulus QC (D19)",
     "Roll yang tersedia dicadangkan otomatis ke SO backorder (urutan FIFO).", "—",
     "SO kembali **Dicadangkan** untuk qty yang sudah ada; sisa tetap backorder (contoh: 38,5 kg dicadangkan, 61,5 kg menunggu transfer CST).", "OK SO-00045"),
    ("C09", "Admin Sales", "`Meja Admin Sales` → [[Ajukan persetujuan]] → [[Konfirmasi]]",
     "Lanjutkan A09–A11 untuk qty yang sudah tersedia; kirim sebagian bila kebijakan *kirim sebagian* aktif, sisa tetap ditunggu.", "—",
     "Tugas gudang lahir hanya untuk qty yang sudah dicadangkan.", ""),
]
