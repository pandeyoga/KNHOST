"""UAT v3.0 — potongan langkah yang dipakai bersama oleh beberapa alur lurus.

Setiap langkah: (peran, navigasi, yang dilakukan / diisi, hasil yang harus terlihat, cek_ui)
cek_ui: "S1"…"S16" = langkah ini sudah dijalankan di layar pada skenario itu (21–22 Okt 2026);
        "=S8" = langkah yang sama persis sudah dijalankan di layar pada skenario S8;
        "" = belum dijalankan di layar — bila tombol/menu tidak ada, catat sebagai temuan.
Setiap fungsi menerima `ui` supaya alur yang memakai potongan sama dengan konteks berbeda (PT lain, gudang lain)
tidak ikut bertanda sudah dicek.
"""

SUKACITA = "pilih **Kerja di: Sukacita** di banner atas bila masuk sebagai *Semua Entitas*"


def pos_order(term="Kredit NET 30 Hari", qc="Tanpa QC", fulfil="kirim", product="CERUTY PREMIUM", tax=False,
              extra_step2="", extra_review="", review_hint="", ui="HP", customer="Toko Kain Sejahtera", special_price=""):
    """Sales membuat pesanan di aplikasi HP (tampil otomatis di layar HP). Checkout = layar yang sama dengan desktop.
    v3.1 (alur hasil trial 22 Okt): pelanggan dipilih di bilah Pelanggan atas katalog (E2), stok PT penjual dipisah dari
    stok grup (B6), tanggal kirim bisa dipilih (E1), harga khusus diminta di checkout untuk pesanan ini (E10).
    Baris yang berubah bertanda belum dicek di layar ("")."""
    ui = "HP" if ui else ""
    rows = [
        ("Sales", "HP: tab **Katalog** → bilah **Pelanggan** (paling atas) → pilih pelanggan",
         f"Pilih *{customer}* lebih dulu — harga pelanggan/harga khusus dan status kredit ikut pelanggan.",
         "Bilah menulis nama pelanggan + lencana kredit (*Kredit aman* / *Mendekati limit* / *Kredit terblokir* / "
         "*Izin kredit disetujui*).", ""),
        ("Sales", "HP: kolom *Cari produk, SKU, warna…* → kartu produk → [[Tambah]] (artikel bervarian: [[Pilih]])",
         f"Cari *{product}* (hasil tampil di bawah *Produk Terlaris*).",
         "Kartu menulis stok **PT penjual** dulu (mis. *Sukacita: 120 yard · 3 roll* atau *Sukacita: kosong*), lalu "
         "*Grup: … roll / … yard* (semua PT). Lembar produk: harga/yard, stok PT & grup, pilihan **Warna**, "
         "*Order biasa / Order sample*, *Per yard / Per Roll*, QTY.", ""),
        ("Sales", "lembar produk → [[Tambah … yard · Rp …]]",
         "Pilih warna, **Order biasa**, **Per yard**, isi QTY.",
         "Bila qty tidak pas roll muncul **Genapkan ke Roll Utuh** (ke atas / ke bawah / potong).", ui),
        ("Sales", "dialog **Genapkan ke Roll Utuh** → [[Pakai Opsi Ini]]",
         "Tanyakan pelanggan lalu pilih *Genapkan ke atas* atau *Genapkan ke bawah*. *Potong roll (pas)* terkunci untuk Sales "
         "(hanya peran berizin potong, mis. Admin Sales).",
         "Tab **Keranjang** berlencana jumlah baris; isi keranjang: produk, *1 roll dipilih*, nilai.", ui),
        ("Sales", "tab **Keranjang** → [[Lanjut ke Checkout]] → langkah 1 → [[Lanjut]]",
         "Pelanggan sudah terisi dari bilah Pelanggan; pilih alamat kirim (*Toko Utama · Pak Hendra*).",
         "Item, nomor roll & qty (mis. 50,95 yard) tampil; langkah 2 terbuka.", ""),
    ]
    step2 = f"**TERMIN PEMBAYARAN**: *{term}*. **REQUEST QC SEBELUM KIRIM**: *{qc}*." + (f" {extra_step2}" if extra_step2 else "")
    exp2 = ("Per item tertulis **Stok Sukacita: … yard** (stok PT penjual; bila kurang: *kurang … (diatur Admin Sales)*); "
            "termin & QC terpilih.")
    if special_price:
        step2 += (f" Pelanggan menawar: pada kartu item → [[Minta Harga Khusus]] → harga diminta **{special_price}** + alasan "
                  "(mis. *pesaing lebih murah*) → [[Simpan]]. Harga khusus ini **hanya untuk pesanan ini**.")
        exp2 += " Kartu item: *Diminta Rp … untuk pesanan ini · diputus Manajer — ubah*."
    rows.append(("Sales", "Checkout langkah 2 *Termin & Lot* → [[Lanjut]]", step2, exp2, ""))
    if fulfil == "kirim":
        meth = "Metode Pemenuhan **Kirim** — tanggal kirim boleh dipilih (tidak boleh lampau) atau dikosongkan."
    else:
        meth = "Metode Pemenuhan **Ambil di Gudang** → isi **Tanggal Pengambilan** (wajib)."
    exp3 = "Pesan *KSC/SO-xxxxx dibuat (reserved) … Grand total Rp …*; pindah ke tab **Pesanan**. **Catat nomor SO.**"
    if special_price:
        exp3 = ("Sebelum buat: kotak **Harga khusus diminta (pesanan ini)** — normal → diminta, *Total harga normal* & "
                "*Total bila disetujui*. Sesudah buat: SO lahir dengan **harga normal**; kartu SO bagian **Sebelum masuk gudang** "
                "menulis *Harga khusus · menunggu Manajer*. **Catat nomor SO.**")
    rows.append(("Sales", "Checkout langkah 3 *Review* → [[Buat Sales Order]]",
                 meth + (" Nyalakan **Minta Faktur Pajak** (pelanggan minta faktur)." if tax else "") +
                 (f" {extra_review}" if extra_review else ""),
                 (f"{review_hint} " if review_hint else "") + exp3, ui if not special_price else ""))
    return rows


def release(ui="", account=None, exp=""):
    """v3.1 (E8) — satu langkah Admin Sales: periksa kelengkapan lalu lepas ke gudang (dulu Verifikasi → Ajukan
    persetujuan → Konfirmasi). Yang masih menunggu ACC Manajer / stok dilepas OTOMATIS sesudahnya."""
    role = ("Admin Sales", account) if account else "Admin Sales"
    return [(role, "`Meja Admin Sales` → antrean **Perlu diperiksa & dilepas ke gudang** → ketik nomor SO di kolom cari → "
             "[[Periksa & lepas]]",
             "Dialog *Periksa & lepas ke gudang*: cocokkan data pesanan (kiri) dengan daftar periksa (kanan) — alamat & penerima, "
             "syarat bayar, isi pesanan, PPN, NPWP bila minta faktur, kredit. *Tahan dulu* dibiarkan kosong → "
             "[[Periksa & lepas ke gudang]].",
             exp or ("Banner *KSC/SO-xxxxx diperiksa & dilepas ke gudang — tugas ambil sudah lahir.* Pelacak SO menunjukkan "
                     "tahap berikutnya & peran pemiliknya."), ui)]


def admin_sales(ui="", account=None, exp=""):
    return release(ui, account, exp)


def pick(ui="S1", badge="", account=None, wh="Jakarta · Gudang Sukacita"):
    role = ("Gudang", account) if account else "Gudang"
    return [
        (role, "`Meja Saya` → antrean **Tugas gudang (terima, picking & kirim)** → baris SO → [[Kerjakan]]",
         f"Buka tugas SO (lencana *Siap diambil*{badge}).",
         f"Pindah ke `Operasi Gudang › Barang Keluar` dengan tugas terpilih ({wh}); panel **AMBIL & KIRIM** memuat "
         "**ROLL YANG HARUS DIAMBIL** (roll, LOT, lokasi, panjang) + *Surat Pengambilan Barang* (Pratinjau / Unduh PDF).", ui),
        (role, "kotak **ROLL YANG HARUS DIAMBIL** → [[Ambil]] (atau scan roll di kolom kode) → [[Kirim Pengambilan]]",
         "Ambil roll fisik sesuai daftar; scan / klik [[Ambil]] tiap roll. Roll yang tidak dialokasikan untuk SO ini ditolak.",
         "Toast *Pengambilan tercatat — Terkumpul x dari x yard*; roll bertanda *sudah diambil*; muncul **Pemeriksaan Muat Akhir** "
         "dan panel **Siap dikirim**. Nama pelanggan tetap tampil.", ui),
    ]


def dispatch(ui="S1", entity="Sukacita", gate=""):
    rows = [
        ("Admin Gudang", f"`Meja Gudang` (pilih **Kerja di: {entity}**) → antrean **Tugas outbound berjalan** → [[Buka WMS]]",
         "Buka tugas SO yang sudah diambil (status *Pengemasan*, diambil x/x).", "Barang Keluar dengan tugas terpilih." +
         (f" {gate}" if gate else ""), ui),
        ("Admin Gudang", "**Pemeriksaan Muat Akhir** → (bila ada *roll belum bertag*) [[Buat tag simulasi]] → [[Mulai Loading Check]] "
         "→ [[Simulasi scan semua (mode UAT)]] → [[Selesaikan]]",
         "UAT tanpa handheld/tag RFID: **Mode simulasi RFID** (disiapkan IT) membuat tag & scan simulasi yang dianggap sah. "
         "Staf Gudang boleh menjalankannya. Tanpa mode simulasi: isi *Alasan override* → [[Override]] (Admin Gudang).",
         "*SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka.* Riwayat scan bertanda *SIMULASI (sah di mode "
         "simulasi UAT)*. Roll di luar SO / kurang → tidak cocok dan kirim tertahan.", "S3" if ui else ""),
        ("Admin Gudang", "panel **Siap dikirim** → [[Kirim Semua]] → [[Kirim Sekarang]]",
         "Kirim seluruh qty yang sudah diambil (atau [[Kirim Sebagian]] + qty). SO dengan beberapa tugas siap di gudang yang "
         "sama: [[Kirim semua tugas SO-… di gudang ini — 1 Surat Jalan]] (satu nomor SJ).",
         "*Terkirim Penuh! … · KSC/SJ-xxxxx* + tombol [[Surat Jalan]] [[Buat Pengiriman]]. **Catat nomor SJ.**", ui),
    ]
    return rows


def logistics(mode="ekspedisi", ui="S1"):
    if mode == "ekspedisi":
        jenis = ("Jenis Pengiriman **Ekspedisi (kurir pihak ketiga)**: ETA, Nama kurir (mis. JNE), No. resi (boleh nanti), "
                 "Layanan (REG), Biaya kirim")
        depart = ("isi **No. resi** → [[Simpan data]] → [[Berangkat]] → [[Dalam perjalanan]]",
                  "Ekspedisi wajib nomor resi sebelum berangkat.")
    else:
        jenis = "Jenis Pengiriman **Armada sendiri**: plat kendaraan (ketik manual bila belum ada di master Armada), sopir (akun atau nama)"
        depart = ("[[Berangkat]] → [[Dalam perjalanan]]", "Armada: plat & sopir sudah terisi di pengiriman.")
    return [
        ("Admin Gudang", "`Meja Gudang` → antrean **Surat Jalan belum diangkut logistik** → ketik nomor SO di kolom cari → [[Buat pengiriman]]",
         f"Modal **Buat Pengiriman**: SJ sudah tercentang (boleh centang SJ lain satu armada); {jenis}; alamat tujuan & telepon "
         "penerima terisi otomatis → [[Buat Pengiriman]].",
         "Nomor **KSC/LG-xxxxx** status *Disiapkan*; detail pengiriman langsung terbuka.", ui),
        ("Admin Gudang", "detail LG → **Foto muat** [[Ambil / unggah]] → [[Tandai Dimuat]] → [[Dimuat]]",
         "Foto barang naik kendaraan. Tanpa foto, tombol Tandai Dimuat tidak aktif.",
         "Status *Dimuat*; muncul [[Berangkat]] · [[Bongkar (kembali ke Disiapkan)]] · [[Gagal kirim]].", ui),
        ("Admin Gudang", "detail LG → " + depart[0], depart[1], "Status *Dalam perjalanan*.", ui),
        ("Admin Gudang", "detail LG → **Bukti terima (POD)** [[Ambil / unggah]] → *Nama penerima* → [[Tandai Terkirim]] → [[Terkirim]]",
         "Di lokasi pelanggan: foto bukti terima; nama penerima terisi dari kontak pelanggan (bisa diubah).",
         "LG *Terkirim* (POD tidak bisa diubah lagi); **SO otomatis Selesai** saat semua SJ ber-POD.", ui),
    ]


def tax_invoice(ui="S1"):
    return [("Finance", f"`Meja Finance` ({SUKACITA}) → antrean **Siap terbitkan Faktur Pajak** → cari SO → [[Terbitkan]]",
             "Hanya bila pelanggan minta Faktur Pajak (PT PKP). Satu klik; NSFP 16 digit menyusul dari Coretax.",
             "Banner *Faktur Pajak KSC/FKT-xxxxx diterbitkan untuk KSC/SO-xxxxx*.", ui)]


def pay(ui="S1", method="Transfer Bank", queue="Uang masuk perlu dicatat & dialokasikan", entity="Sukacita"):
    return [("Finance", f"`Meja Finance` (Kerja di: {entity}) → antrean **{queue}** → cari nomor SO → [[Catat kwitansi]]",
             f"Dialog *Catat Pembayaran*: Metode **{method}**, Tanggal, tab **Manual per Pesanan** (SO ini di urutan teratas, "
             "nominal terisi) → [[Simpan Pembayaran]].",
             "*Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk …* Baris hilang dari antrean.", ui)]


def journey(ui="HP", extra=""):
    return [("Sales", "HP: tab **Pesanan** → kolom cari nomor SO → ketuk kartu SO",
             "Periksa kartu SO: item, total, termin, dan **PERJALANAN PESANAN**.",
             "Perjalanan **100%**: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · "
             "Diterima pelanggan · Ditagih (Faktur Komersial) · Dibayar *Lunas*; **Sisa tagihan Rp 0**; status kartu *Lunas*."
             + (f" {extra}" if extra else ""), "HP" if ui else "")]


def deliver_and_pay(mode="ekspedisi", ui="S1", tax=False, pay_ui=None):
    rows = dispatch(ui) + logistics(mode, ui)
    if tax:
        rows += tax_invoice(ui)
    rows += pay(pay_ui if pay_ui is not None else ui) + journey(ui)
    return rows
