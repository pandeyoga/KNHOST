"""UAT v3.0 — 16 alur end-to-end LURUS (satu cabang = satu alur utuh, dibaca dari atas ke bawah tanpa melompat).

Struktur SCENARIOS: kode, judul, kapan cabang ini terjadi, kelompok, mulai, menit, peran, data, perbaikan terkait,
status cek UI ("full" / "partial" / "none"), langkah.
"""
import v3_steps as s

KANDA_SALES = ("Sales", "sales.kanda@kainnusantara.id")
KANDA_ADM = "salesadmin.kanda@kainnusantara.id"
WH_RCM = ("Gudang", "warehouse.rancamalang@kainnusantara.id")
CST_ADM = ("CST", "salesadmin.cst@kainnusantara.id")


def AP_STEPS(note, ui=""):
    """Hutang supplier: tagihan, kontrabon & PEMBAYARAN = Manajer/Admin (izin vendor_bill.pay); Finance tidak berwenang."""
    return [("Pembelian", "`Pembelian › Hutang Pemasok › Tagihan Supplier` → [[Buat Tagihan]] → pilih PO → No. faktur supplier → "
             "[[Submit & Posting]]",
             f"Tagihan dicocokkan PO ↔ penerimaan ↔ bill (3-way). {note}",
             "*Vendor Bill VB-xxxxx dibuat — langsung di-posting (match bersih)*; total + PPN masukan; status *Terposting*.", ui),
            ("Pembelian", "Tagihan Supplier → baris VB → [[Bayar]] (nominal terisi sisa hutang) → [[Catat Pembayaran]]",
             "Pembayaran hutang = Manajer/Admin (keputusan pemilik: Finance tidak memegang sisi hutang). "
             "Kontrabon (Tukar Faktur) opsional bila supplier menagih lewat tukar faktur.",
             "VB *Lunas*; *Sudah dibayar* = total; jurnal terposting.", ui)]


# v3.1 (alur hasil trial 22 Okt 2026) — teks bersama untuk langkah yang berubah (belum dicek di layar).
KURANG = "Banner *KSC/SO-xxxxx diperiksa — kurang stok: lanjut [Putuskan pemenuhan]; dilepas otomatis saat stok tersedia.*"
AUTO = "**SO otomatis dilepas ke gudang** (sudah diperiksa Admin Sales) — tugas ambil lahir tanpa langkah Admin Sales lagi."
SPK_MD = ("SPK penerimaan = **MD Quality saja** (warna & handfeel). Rencana QC bawaan *Tidak wajib (QC kapan saja)* → SPK MD "
          "bisa ditutup tanpa menunggu QC 4-point.")


def QC4(ui=""):
    """QC 4-point tersendiri (E9/F5): Lembar Inspect; grade roll dipilih petugas — sistem tidak mengisi otomatis."""
    return ("QC (opsional)", "SPK MD → [[Buat SPK QC 4-point]] (boleh kapan saja) → SPK QC → **Lembar Inspect** → per roll: Yds, "
            "lebar (inci), sel KODE+POIN per 15 yd (mis. *CG2 KO1*), **Grade roll**, Grade A/A1/B (yd), Perbaikan, Ket. → "
            "[[Simpan lembar]] → [[Tutup SPK]]",
            "Grade roll **dipilih petugas** dari total poin — sistem tidak mengisi otomatis; kode cacat bebas (artinya "
            "ditafsirkan petugas); Grade A/A1/B (yd) = catatan pembagian panjang. [[Cetak lembar]] menyerupai kertas "
            "*DATA HASIL INSPECT*.",
            "Poin & STDRT terhitung per roll; tanpa grade → *Pilih grade roll: RL-…*. Roll yang ditolak QC **ditahan**.", ui)


def _s1():
    return (s.pos_order(tax=True) + s.admin_sales() + s.pick() + s.dispatch() + s.logistics("ekspedisi") +
            s.tax_invoice() + s.pay() + s.journey())


def _s2():
    return (s.pos_order(term="CBD — Bayar Sebelum Kirim", ui="S2",
                        review_hint="Kotak **Pemenuhan** memberi tahu: *Termin CBD wajib dibayar 100% (Rp …) sebelum kirim — "
                                    "pengiriman tertahan sampai Finance mencatat pembayaran*.") +
            s.release(exp="Banner *KSC/SO-xxxxx diperiksa & dilepas ke gudang — tugas ambil sudah lahir.* Pelacak SO: tahap "
                          "berikutnya *Dibayar sesuai termin CBD sebelum kirim — Finance*.") +
            s.pick("S2", badge=" + **tertahan bayar**") +
            [("Gudang", "`Barang Keluar` → tugas SO (lencana **TERTAHAN BAYAR · CBD**) → panel kirim",
              "Coba kirim.",
              "Kotak merah *Tertahan — belum dibayar sesuai termin* (wajib Rp …, sudah dibayar Rp 0, kurang Rp …); "
              "[[Kirim Sebagian]] / [[Kirim Semua]] **nonaktif** dengan alasan.", "S2"),
             ("Finance", f"`Meja Finance` ({s.SUKACITA}) → antrean **Menunggu pembayaran sebelum kirim (CBD/DP)** → [[Catat kwitansi]]",
              "Pelanggan sudah transfer. Dialog *Catat Pembayaran*: SO ini di urutan teratas & nominal terisi → [[Simpan Pembayaran]]. "
              "Cara lain: detail SO → kotak termin → [[Catat pembayaran (Rp …)]].",
              "*Pembayaran KSC/AR-xxxxx dicatat*; SO keluar dari antrean; kiriman otomatis terbuka.", "S2"),
             ("Finance / Manajer", "detail SO → kotak termin → [[Beri pengecualian kirim]] (hanya bila belum bayar tapi harus kirim)",
              "Opsional: isi alasan (min. 5 huruf) → [[Simpan pengecualian]]. Dapat dicabut lagi dengan alasan.",
              "*Boleh kirim — pengecualian berizin* + pelaku, waktu, alasan. Gudang & Sales tidak punya tombol ini.", "S2")] +
            s.dispatch("S2", gate="Kotak hijau *Boleh kirim — termin terpenuhi* (sudah dibayar Rp …).") +
            s.logistics("armada", "S2") +
            s.journey("S2", "Uang masuk KSC/AR-xxxxx tampil; tanggal *Dibayar* lebih awal dari *Dikirim*."))


def _s3():
    return (s.pos_order(term="Tunai / POS", fulfil="ambil", ui="S3",
                        review_hint="Ringkasan *Diambil oleh … · Ambil di gudang · tanggal* (tanggal tidak boleh lampau).") +
            s.admin_sales() +
            [("Gudang", "`Meja Saya` → **Tugas gudang** → baris SO → [[Kerjakan]] (tugas *Terjadwal*) → [[Rilis ke Antrean]]",
              "Tugas ditahan sampai tanggal ambil; [[Kerjakan]] langsung membuka tugas terjadwalnya. Pelanggan datang lebih awal → rilis.",
              "Kotak ungu *Barang baru disiapkan pada/setelah tanggal ambil*; setelah rilis tugas masuk antrean pengambilan.", "S3")] +
            s.pick("=S1") + s.dispatch("S3") +
            [("Admin Gudang", "`Gudang & Logistik › Pengiriman` → [[Buat Pengiriman]] (SJ tadi) → jenis **Diambil pelanggan** (otomatis)",
              "Pesanan *Ambil di gudang* otomatis memakai mode pickup; simpan. Sales memberi **kode pickup** (tampil di kartu HP).",
              "Pengiriman *Menunggu diambil*; HP: kartu SO menampilkan *Diambil di gudang · tanggal* & kode pickup.", "S3"),
             ("Admin Gudang", "detail pengiriman → [[Verifikasi & serahkan]]",
              "Pelanggan datang: ketik **kode pickup** + nama & nomor identitas pengambil.",
              "Kode salah → *KODE PICKUP SALAH — barang tidak boleh diserahkan*. Benar → *Diserahkan*; SO *Selesai*.", "S3")] +
            s.pay(ui="S3", method="Tunai") + s.journey("S3", "Perjalanan pesanan 100% · kode pickup tampil."))


def _s4():
    return (s.pos_order(ui="=S1", special_price="Rp 17.500") +
            s.release(exp="Banner *KSC/SO-xxxxx diperiksa — menunggu ACC Manajer; dilepas ke gudang otomatis sesudah ACC.* "
                          "SO pindah ke antrean **Menunggu keputusan manajer**.") +
            [("Manajer", "`Meja Saya` → **Permintaan harga khusus** → [[Putuskan]] (atau `Pusat Persetujuan › Inbox Persetujuan`)",
              "Bandingkan harga normal vs diminta & alasan → [[Tolak]] + catatan (mis. *margin terlalu tipis*).",
              "Entri *ditolak* + pemutus & catatan. `Meja Admin Sales`: SO di antrean **Harga khusus ditolak — menunggu sales**.", ""),
             ("Sales", "HP: tab **Pesanan** → ketuk SO → kotak **Persetujuan** → entri **DITOLAK** → [[Ajukan harga lain]] → [[Ajukan]]",
              "Baca *Catatan pemutus*. Tiga pilihan: **Ajukan harga lain** · **Lanjut harga normal (Rp …)** · **Batalkan pesanan**. "
              "Nego ulang → harga baru (mis. Rp 19.000) + lampiran bukti chat/penawaran (**wajib**) → [[Ajukan]].",
              "Entri lama *Digantikan pengajuan baru*; entri baru *MENUNGGU*. (Bila memilih *Lanjut harga normal*: SO dilepas "
              "otomatis dengan harga normal. *Batalkan pesanan* + alasan: booking stok dilepas.)", ""),
             ("Manajer", "`Meja Saya` → **Permintaan harga khusus** → [[Putuskan]] → [[Setujui]]",
              "Setujui harga baru + catatan.",
              "Harga baris = harga khusus; subtotal, PPN, grand total dihitung ulang; " + AUTO, "")] +
            s.pick("=S1") + s.dispatch("=S3") + s.logistics("ekspedisi", "=S1") +
            s.pay("=S1") + s.journey("S4", "Langkah *Disetujui* mencatat manajer pemutus harga khusus."))


def _s5():
    return ([(KANDA_SALES, "HP: tab **Katalog** → bilah **Pelanggan** → *CV Garmen Soreang Jaya* → cari *LYFLEX ACTIVE BEIGE A* → "
              "[[Pilih]] (artikel bervarian) → varian *BEIGE · A* → qty kg → [[Tambah …]] → tab **Keranjang**",
              "Limit kredit pelanggan **Rp25 jt**. Qty sampai nilai melewati limit (mis. ±700 kg × Rp41 rb ≈ Rp28,7 jt).",
              "Lencana **Kredit terblokir** + kotak merah *Pelanggan ini tidak bisa membeli — … Checkout terkunci sampai izin kredit "
              "disetujui Manajer*; tombol checkout berubah **Kredit terblokir — tidak bisa checkout**.", ""),
             (KANDA_SALES, "kotak merah di bilah Pelanggan → [[Ajukan Override Kredit (Rp …)]] → alasan → [[Ajukan]]",
              "Isi alasan (min. 5 huruf, mis. *pelanggan lama, pembayaran lancar*).",
              "*Override kredit diajukan — menunggu persetujuan Manajer/Finance. Setelah disetujui, buka lagi checkout ini lalu "
              "[Buat Sales Order].*", ""),
             ("Manajer", "`Pusat Persetujuan › Inbox Persetujuan` → entri **Override kredit** → [[Tinjau & Putuskan]] → [[Setujui]]",
              "Tinjau limit, eksposur, umur piutang; catatan (mis. *ACC direksi via WA*).", "Override *disetujui*.", "S5"),
             (KANDA_SALES, "HP: Keranjang (lencana kini **Izin kredit disetujui**) → [[Lanjut ke Checkout]] → termin *Kredit NET 30 Hari* → "
              "langkah 3 → [[Buat Sales Order]]",
              "Checkout terbuka lagi. Tanpa izin, server menolak SO (*Kredit … terblokir — pesanan tidak bisa dibuat*); SO tidak lahir.",
              "SO **KANDA/SO-xxxxx** dibuat.", "")] +
            s.release(account=KANDA_ADM) +
            s.pick("S5", account="warehouse.soreang@kainnusantara.id", wh="Soreang · Gudang Kanda") +
            s.dispatch("S5", entity="Kanda Fabric") + s.logistics("armada", "=S2") +
            s.pay("=S1", entity="Kanda Fabric") + s.journey("=S1"))


def _s6():
    return (s.pos_order(qc="QC seluruh roll", ui="S6") + s.admin_sales() +
            [("Gudang", "`Operasi Gudang › Cutting` → bagian **Potong roll untuk pesanan (SO)** → pilih gudang → **Antrean Potong Roll** → "
              "panjang aktual → [[Konfirmasi Potong]] → scan/ketik label roll anak → [[Verifikasi]]",
              "Bila daftar roll menulis *Potong dulu*: potong, cetak label roll anak, verifikasi label (tanpa RFID). Antrean yang sama "
              "masih ada di `Lokasi Rak`.",
              "Roll anak *terverifikasi*; muncul di daftar ambil.", "")] +
            s.pick("S6") +
            [("Gudang", "`Barang Keluar` → panel **Siap dikirim** → [[Kirim Semua]]", "Coba kirim sebelum QC.",
              "Ditolak: *SO meminta QC … kirim menunggu SPK QC selesai*.", "S6"),
             ("Admin Gudang", "`Meja Gudang` → antrean **Pesanan minta QC — SPK belum dibuat** → [[Buka]] → `QC & Inspeksi` → [[Buat SPK Inspeksi]]",
              "Jenis **QC Permintaan Pesanan (SO)** → pilih SO → simpan → [[Tugaskan]] petugas QC.",
              "SPK *Ditugaskan*; muncul di antrean QC.", "S6"),
             ("QC", "`Operasi Gudang › QC & Inspeksi` → Dokumen Inspeksi → SPK → [[Mulai periksa]] → baris roll [[QC 4-point]] → [[Simpan hasil]]",
              "Per roll: panjang diinspeksi (**yard**), cacat per nilai poin 1–4, dan **Grade hasil QC** dipilih petugas (sistem tidak "
              "mengisi grade otomatis).",
              "Hasil per roll + grade pilihan petugas tersimpan; tanpa grade → *Pilih grade roll — grade ditentukan petugas QC dari "
              "total poin*.", ""),
             ("Admin Gudang", "SPK → **Keputusan akhir** (Diterima seluruhnya / sebagian / turun grade / Ditolak) → [[Tutup SPK]]",
              "Satu keputusan SPK. Roll tidak lulus → Admin Sales **Ganti Roll** lalu QC ulang roll pengganti.",
              "SPK *Selesai*; pesan tahan QC hilang dari panel kirim.", "S6")] +
            s.dispatch("S6") + s.logistics("ekspedisi", "=S1") + s.pay("=S1") + s.journey("=S1"))


def _s7():
    return ([("Sales", "HP: tab **Katalog** → cari *ALICE KNIT (94139-45) 14 A* → [[Pilih]] (artikel bervarian) → varian *14 · A* → qty **100 kg** → pilih **Pesan dengan backorder** → tab **Keranjang** → [[Lanjut ke Checkout]]",
              "Langkah 1: pelanggan *Toko Kain Sejahtera*. Langkah 3: ringkasan menyebut qty backorder (termasuk dari PT lain) → [[Buat Sales Order]].",
              "SO **Menunggu stok**; *Sebagian via backorder*.", "S7")] +
            s.release(exp=KURANG) +
            [("Admin Sales", "`Meja Admin Sales` → antrean **Perlu dipenuhi (kurang stok)** → [[Putuskan pemenuhan]]",
              "Dialog **Rencana pemenuhan** (sama dengan dari halaman pesanan): stok sendiri, **Transfer dari Cipta Sandang** "
              "(stok & harga internal), PO ke supplier, tunggu barang. Isi transfer 100 kg → [[Jalankan rencana]]. Opsional: "
              "[[Pilih roll (n tersedia)]] untuk memilih roll tertentu (qty = jumlah panjang roll terpilih).",
              "**Transaksi Antar-PT KSC/IC-xxxxx** terbentuk & tertaut ke SO; roll pilihan tercatat di permintaan.", ""),
             (WH_RCM, "`Akuntansi & Pajak › Antar Entitas (Grup)` (Kerja di: Cipta Sandang) → transaksi IC → [[Buat Tugas Gudang]]",
              "Gudang PT pemasok menyiapkan barang (izin langkah mengikuti peran: Gudang boleh membuat tugas gudang).",
              "Tugas gudang IC lahir; transfer gudang *Menunggu persetujuan*.", "S7"),
             (("Admin Gudang CST", "whadmin@kainnusantara.id"), "`Operasi Gudang › Stok, Transfer & Opname › Transfer` → transfer → [[Setujui]]",
              "Admin Gudang yang memegang PT Cipta Sandang menyetujui transfer.",
              "Transfer *Disetujui → Selesai*; pemilik roll = Sukacita; **SO Dicadangkan** untuk qty yang tersedia; " + AUTO, "")] +
            s.pick("=S1", account=WH_RCM[1], wh="Rancamalang · Gudang Knitting") +
            s.dispatch("=S3") + s.logistics("armada", "=S2") + s.pay("=S1") + s.journey("=S1"))


def _s8():
    return ([("Sales", "HP: tab **Katalog** → *ALICE KNIT 14 A* **100 kg** → Checkout + backorder → [[Buat Sales Order]]",
              "Sama dengan S7 langkah 1.", "SO **Menunggu stok**.", "=S7")] +
            s.release(exp=KURANG) +
            [("Admin Sales", "`Meja Admin Sales` → **Perlu dipenuhi (kurang stok)** → [[Putuskan pemenuhan]]",
              "**PO ke supplier (lewat PR)** → [[maks]] → [[Jalankan rencana]]. Artikel wajib punya *Sumber restock* (contoh: ALICE KNIT = supplier); "
              "artikel tanpa sumber restock ditolak dengan pesan *minta MD mengisi Master Produk › Sumber Restock*.",
              "*Penuh — … PO ke supplier (PR-xxxxx)*; PR merujuk SO.", "S8"),
             ("Pembelian", "`Pembelian › Pengadaan › Permintaan Pembelian` → PR → [[Realisasi ke PO]] → pilih supplier (mis. *PT Kimia Warna Prima*) → [[Buat PO]]",
              "Harga otomatis (kontrak → estimasi PR → barang supplier → price-list → master). PR ≥ Rp50 jt / PO ≥ Rp100 jt → ACC dulu "
              "(oleh akun lain — pemisahan tugas).",
              "**PO KSC/PO-xxxxx**; PR *Terealisasi Penuh*; qty PO = *incoming*.", "S8"),
             ("Supplier", "di luar sistem", "Supplier mengirim barang + Surat Jalan bernomor PO.", "—", ""),
             ("Admin Gudang", "`Operasi Gudang › Barang Masuk` → [[Kedatangan baru]] → **Supplier (PO)** → mitra → [[Lanjut]] → [[Buat kedatangan]] → [[Isi manual]]",
              "Kepala SJ (nomor, tanggal, nama pengirim) → [[Simpan kepala SJ]] — dibuka dari PO: *Nomor PO di SJ* sudah terisi. "
              "Baris: pilih **Target** = baris PO lebih dulu → kode, deskripsi, satuan & PO yang kosong terisi otomatis (ketik kode/nama "
              "versi supplier → muncul **Saran target**); lengkapi qty SJ, jumlah roll, LOT → [[Baris]]. (Foto SJ boleh menyusul.)",
              "**KSC/GRN-xxxxx** *Draf → Tinjau SJ*; baris *Siap*.", ""),
             ("Gudang", "kedatangan → [[Mulai hitung fisik]] → per roll isi panjang/berat & LOT → [[Roll manual]] (atau scan label supplier) → [[Selesai hitung]]",
              "Per roll catat fisik; pilih **satuan panjang** (satuan SJ/PO atau satuan stok) — sistem mengonversi ke satuan stok. "
              "Nomor roll KN lahir otomatis.",
              "Roll lahir status *receiving*, daftar roll tampil dua satuan (mis. *109,36 yard (= 100 meter)*); tab **Rekonsiliasi** "
              "terbuka.", ""),
             ("Admin Gudang", "**Rekonsiliasi** → (selisih di luar toleransi: [[Terima dengan catatan]] + alasan / [[Klaim ke supplier]]) → [[Tutup Penerimaan]]",
              "Selisih dalam toleransi → *Cocok*. Di luar toleransi = pemblokir sampai diputuskan.",
              "GRN *Ditutup*, baris *Terposting*; stok bertambah sebesar fisik; roll **karantina**; **SPK inspeksi (INS) MD Quality** "
              "otomatis.", "S8"),
             ("Admin Gudang", "`Meja Gudang` → **SPK inspeksi belum ditugaskan** → cari nomor PO → [[Tugaskan]] → pilih petugas → [[Tugaskan]]",
              SPK_MD, "SPK *Ditugaskan*. MD Quality baru bisa mengisi sesudah ini (F-13).", ""),
             ("MD Quality", "halaman awal **Dokumen Inspeksi (INS)** (Kerja di: Sukacita) → SPK → baris roll [[MD Quality]]",
              "Hasil banding warna & handfeel (sesuai / beda / tidak bisa diterima), skor handfeel 1–5, potong uji (opsional) → [[Simpan hasil]].",
              "Kolom WARNA/HANDFEEL per roll terisi; *MDQ: nama*.", "S8"),
             ("Admin Gudang", "SPK MD → **Keputusan akhir** → *Diterima seluruhnya* / sebagian / turun grade / ditolak → [[Tutup SPK]]",
              "**Satu keputusan** (F-14): diterima langsung lepas karantina; ditolak → disposisi (rusak / retur ke supplier → Nota Debit).",
              "SPK *Selesai*; roll **tersedia**; sistem mencadangkan ke SO backorder → SO **Dicadangkan** (sisa SJ kurang tetap "
              "backorder); " + AUTO, ""),
             QC4()] +
            s.pick("=S1") + s.dispatch("=S3") + s.logistics("ekspedisi", "=S1") + s.pay("=S1") +
            s.journey("=S1") + AP_STEPS("Tagihan = qty **diterima**, bukan qty SJ.", ui="S8"))


def _s9():
    return ([("Sales", "HP: tab **Katalog** → artikel makloon contoh (*RIVERA RIB BW A*) → Checkout + backorder → [[Buat Sales Order]]",
              "Pesan melebihi stok jadi (sisa jadi backorder).", "SO **Dicadangkan** sebagian + backorder.", "=S7")] +
            s.release(exp=KURANG) +
            [("Admin Sales", "**Perlu dipenuhi (kurang stok)** → [[Putuskan pemenuhan]] → *PO ke supplier (lewat PR)* → [[Jalankan rencana]]",
              "Jalur PR mengikuti sumber restock artikel (RIVERA RIB = makloon).", "PR lahir dengan baris *Makloon*.", "S9"),
             ("Pembelian", "`Permintaan Pembelian` → PR → baris *Makloon* → [[Buat Order Makloon]] (Wizard)",
              "Wizard terisi dari **Resep Proses** (bahan, mitra, yield, kontrak): langkah 1 bahan & gudang (qty bahan dihitung dari resep), "
              "langkah 2 rantai proses (tarif kontrak), langkah 3 ringkasan → [[Simpan Order Makloon]]. "
              "Tanpa resep → pesan *Buat resep dulu (Pembelian → Master Pembelian → Resep Proses)*.",
              "**MKO-xxxxx** (`Pesanan Pembelian › Order Makloon`) *Draf*; bahan *dicadangkan* (fisik belum berkurang).", "S9"),
             ("Gudang", "`Pembelian › Pesanan Pembelian › Order Makloon` → MKO → [[Detail →]] → langkah 1 [[Issue ke Makloon]] → [[Issue Sekarang]]",
              "Gudang sumber dipilih otomatis yang stoknya cukup.", "Stok bahan keluar **tepat sekali** (fisik berkurang); MKO *Diproses*.", "S9"),
             ("Mitra", "di luar sistem", "Mitra memproses & mengirim hasil + SJ.", "Hasil aktual boleh ≠ rencana.", ""),
             ("Admin Gudang", "`Barang Masuk` → [[Kedatangan baru]] → **Makloon (MKO)** → mitra → SJ manual → Target = *MKO langkah 1* → "
              "[[Mulai hitung fisik]] → [[Selesai hitung]] → [[Tutup Penerimaan]]",
              "Sama dengan S8; bisa *Terima sebagian* bila hasil dikirim bertahap.",
              "GRN *Ditutup*; MKO *Selesai*; roll hasil **tersedia** & **SO backorder otomatis dicadangkan**; sisa cadangan bahan dilepas; "
              + AUTO + " QC hasil makloon (opsional): `QC & Inspeksi` → [[Buat SPK Inspeksi]] jenis *Hasil Makloon*.", "")] +
            s.pick("=S1") + s.dispatch("=S3") + s.logistics("ekspedisi", "=S1") + s.pay("=S1") + s.journey("=S1"))


def _s10():
    return ([(("Sales CST", "sales.cst@kainnusantara.id"), "HP: tab **Katalog** → woven (*SHAKILA LAK*) + knit (*ALICE KNIT 8 A*) yang stoknya di Rancamalang → Checkout → [[Buat Sales Order]]",
              "PT **Cipta Sandang** (pemilik stok Rancamalang); pelanggan Jakarta (*PT Fashion Ibukota*).",
              "SO *Dicadangkan*; alokasi per gudang (Woven / Knitting).", "=S1")] +
            s.admin_sales(account="salesadmin.cst@kainnusantara.id") +
            [(WH_RCM, "`Operasi Gudang › Cutting` → **Potong roll untuk pesanan (SO)** → gudang Rancamalang (bila ada baris *Potong dulu*)",
              "Potong & verifikasi label roll anak.", "Roll anak terverifikasi & berkomitmen ke SO.", ""),
             (WH_RCM, "`Operasi Gudang › Stok, Transfer & Opname › Transfer` → [[Buat Transfer]] → asal *Rancamalang · Gudang Woven* → "
              "tujuan *Rancamalang · Gudang Transit* → **Untuk memenuhi SO** = SO ini → centang roll → [[Tambahkan roll SO terpilih]] → [[Buat Transfer]]",
              "Lakukan **sebelum** barang diambil. Ulangi untuk *Gudang Knitting → Transit*. SO yang sudah mulai diambil tidak ditawarkan.",
              "**CST/TRF-xxxxx** *Menunggu Persetujuan*; roll tetap terkunci untuk SO.", "S10"),
             (("Admin Gudang CST", "whadmin@kainnusantara.id"), "`Operasi Gudang › Stok, Transfer & Opname › Transfer` → baris transfer → [[Setujui]] "
              "(menolak: [[Tolak]] + alasan)",
              "Cek asal, tujuan & roll SO di detail transfer.", "Transfer *Disetujui*.", "S10"),
             (WH_RCM, "detail transfer → [[Mulai Pengambilan]] → [[Siap Muat (Staging)]] → [[Berangkatkan (Dalam Perjalanan)]]",
              "Perjalanan internal antargudang (bukan pengiriman pelanggan); Surat Jalan Transfer bisa dicetak dari detail.",
              "Transfer *Dalam Perjalanan*.", "S10"),
             (WH_RCM, "detail transfer → panel **Penerimaan** (Gudang Transit) → scan/ketik nomor roll satu per satu → [[Terima roll terpilih (n)]]",
              "Roll tidak datang/rusak → **Pengecualian (n terbuka)**: [[Kembalikan ke gudang asal]] / [[Laporkan hilang]] / [[Tutup dengan catatan]].",
              "Transfer *Selesai*; roll di Transit tetap *berkomitmen* ke SO; **tugas pengambilan pindah ke Gudang Transit**.", "S10")] +
            s.pick("S10", account=WH_RCM[1], wh="Rancamalang · Gudang Transit") +
            [(WH_RCM, "`Barang Keluar` → tugas lain SO yang sama", "Scan roll milik tugas lain / gudang lain.",
              "Ditolak: *Roll … tidak ditemukan untuk produk tugas ini*.", "S10")] +
            s.dispatch("=S3", entity="Cipta Sandang") + s.logistics("armada", "=S2") + s.pay("=S1", entity="Cipta Sandang") +
            s.journey("=S1", "Rantai: SO → transfer ke Transit → ambil di Transit → SJ pelanggan → POD."))


def _sample(paid):
    ui = "S12" if paid else "S11"
    rows = [("Sales", "HP: tab **Katalog** → kartu produk → [[Tambah]] (artikel bervarian: [[Pilih]]) → **Order sample**",
             "Pilih jenis **Standar** (woven ≤ 5 yd, knit ≤ 2 kg) / **Hanger** (≤ 0,5 yd) / **Catalogue**; qty → [[Tambah Sample (… yard)]]. "
             "Sample tidak bisa dicampur baris biasa.",
             "Keranjang **Sample**; melebihi batas → ditolak (*jual sebagai ECER berbayar*).", ui),
            ("Sales", "tab **Keranjang** → [[Lanjut ke Checkout]] → pelanggan → [[Lanjut]] → skema **" + ("Sample Berbayar" if paid else "Sample Gratis") +
             "** → [[Lanjut]] → tanggal: *Disesuaikan Admin Sample* → [[Buat Pesanan Sample (" + ("Berbayar" if paid else "Gratis") + ")]]",
             "Tanggal kirim sample boleh diserahkan ke Admin Sample.",
             "**KSC/SOS-xxxxx** (terpisah dari SO); " + ("harga × panjang + PPN; *Menunggu persetujuan bayar sample*." if paid else "kartu HP *Gratis* tanpa tombol bayar."), ui)]
    if paid:
        rows.append(("Finance", "`Meja Finance` → **Sample berbayar — menunggu ACC bayar** → [[Tinjau]] → [[Setujui Pembayaran]] "
                     "(atau `Penjualan › Pesanan Sample` filter *Menunggu ACC bayar*)",
                     "Pastikan pembayaran / kesepakatan bayar ada (Admin Sample juga berwenang).",
                     "SOS *Disetujui*. Sales tidak punya tombol; teruskan sebelum disetujui → ditolak.", ui))
    rows += [("Admin Sample", "`Meja Sample` → **Siap diteruskan ke gudang** → [[Teruskan ke Gudang]]",
              "Teruskan; catalogue boleh ganti warna *soft* (berjejak).", "SOS pindah ke *Sedang dipotong / disiapkan gudang*.", ui),
             ("Gudang", "`Operasi Gudang › Cutting` → tab **Belum dipotong** → kartu paket SOS (satu kartu per pesanan × gudang) → "
              "[[Potong semua (n) · roll saran]]",
              "Pesanan catalogue = **satu paket** berisi semua baris (bukan tugas satu per satu). Roll saran tidak tersedia → dipilih "
              "ulang FIFO. Perlu roll lain: [[Potong manual]] + roll + alasan. (Cara lama tetap ada: `Meja Saya` → **Sample untuk "
              "dipotong** → [[Potong]].)",
              "*Sample dipotong — RL-… → RL-…-n · panjang*; paket pindah ke tab **Menunggu Admin Cutting**; nilai SOS mengikuti "
              "panjang aktual.", "")]
    if paid:
        rows.append(("Finance", "`Meja Finance` → **Sample berbayar — menunggu ACC bayar** (lencana *ACC ulang*) → [[Tinjau]] → [[Setujui Ulang Pembayaran (Rp …)]]",
                     "Selisih ≤ ±5% → tagihan menyesuaikan otomatis. Di atas 5% (mis. 3 → 3,5 yd) → **persetujuan ulang** (F-15).",
                     "*Pembayaran disetujui*; kirim tertahan sampai disetujui ulang.", ui))
    rows += [("Admin Sample", "`Penjualan › Pesanan Sample` → tab **Meja Cutting** → [[Terima semua potongan SOS-… (n baris)]]",
              "Terima potongan dari gudang (Admin Cutting) sekaligus; per baris tetap bisa [[Terima hasil potong]].",
              "Pindah ke *Diterima Admin Cutting — siap kirim/ambil*. Kirim sebelum diterima → ditolak *belum diterima Admin Cutting*.", ""),
             ("Gudang", "`Barang Keluar` → filter jenis **Sample** / cari nomor SOS → tugas **SAMPEL** → cek muat simulasi (lihat S1) → "
              "[[Kirim semua tugas SOS-… di gudang ini — 1 Surat Jalan]] → [[Kirim Sekarang]]",
              "Tugas sample baru tampil sesudah diterima Admin Cutting. Semua baris paket dikirim dengan **satu** Surat Jalan.",
              "*Barang terkirim — No. Surat Jalan KSC/SJ-xxxxx* (satu nomor untuk semua baris); SOS *Dikirim*.", "")]
    rows += s.logistics("ekspedisi", "=S1")
    if paid:
        rows += [("Finance", "`Meja Finance` → **Uang masuk** → [[Catat kwitansi]] → SOS dengan nilai **aktual**",
                  "Catat pembayaran sample.", "SOS lunas.", "=S1")]
    rows += [("Sales", "HP: tab **Pesanan** → kartu SOS", "Periksa status akhir.",
              "SOS *Dikirim/Selesai*" + (" & lunas." if paid else " · *Gratis*."), ui)]
    return rows


def _s13():
    return [
        ("Sales", "HP: tab **Lainnya** › **Pesanan Khusus (OD)** → [[Ajukan pesanan khusus]]",
         "Bagian 1: pelanggan, judul permintaan. Bagian 2: **Item 1** = A 100 m (jenis uji *Printing*), "
         "[[Tambah item]] **Item 2** = B 200 m (jenis uji *Labdip*); sumber desain; satuan.",
         "Formulir 6 bagian; pesan *Belum lengkap: …* menyebut isian yang kurang.", "S13"),
        ("Sales", "formulir OD → bagian 3–6 → **Tenggat kirim** → centang *Langsung ajukan untuk persetujuan Manajer* → [[Simpan pesanan khusus]]",
         "Referensi pelanggan, warna target, foto swatch (opsional), **tenggat kirim**, catatan.",
         "**SORD-yymmdd-xxxx** (tanggal WIB) *Menunggu persetujuan*.", "S13"),
        ("Manajer", "`Penjualan › Pesanan Khusus` → baris OD → [[Detail →]] → [[Setujui]] (Inbox Persetujuan: [[Buka layarnya]])",
         "Rantai persetujuan berjenjang.",
         "Pesan hijau *Pesanan disetujui. Diteruskan otomatis: KSC/DSR-…, KSC/SMP-…*; DSR (printing) & SMP per item tercatat atas nama "
         "Sales pembuat OD; lencana kepala OD mengikuti fase (*Desain berjalan* → *Sampling berjalan* …), riwayat status mencatat *Disetujui*.", "S13"),
        ("MD", "`Meja MD` → **Permintaan desain** (*belum ditugaskan*) → [[Buka]] → [[Tugaskan]]",
         "Pilih desainer (*Intan*) & tenggat.", "DSR *Ditugaskan*; hilang dari antrean MD sampai desain diserahkan.", "S13"),
        ("Desainer", "`Meja Saya` → DSR → [[Buat Desain Baru]] → unggah artwork → centang **Print paper** → [[Ajukan untuk review]]",
         "Kerjakan artwork ronde ini.", "DSR *Menunggu keputusan*; versi & checklist per ronde.", "S13"),
        ("Manajer", "DSR → [[Mulai review]] → [[Setujui (ACC) + nilai akhir]]",
         "Manajer = PIC/penilai desain (revisi: [[Minta revisi]] + alasan → kembali ke desainer).",
         "DSR *Disetujui (ACC)*; sample proofing item A siap dikirim ke supplier.", "S13"),
        ("MD", "`R&D › Permintaan Sample` → [[Daftar]] → SMP item → [[Detail]] → **Spesifikasi produk target** → [[Ubah]] → isi **Gramasi** & **Lebar (cm)** → [[Simpan perubahan]]",
         "OD dari HP belum membawa gramasi/lebar — **wajib dilengkapi sebelum pemenang dipilih** agar SKU langsung lahir. "
         "Bila terlewat: Meja MD menampilkan *SKU belum lahir · lengkapi spesifikasi*.",
         "Spesifikasi *Draf* dengan gramasi & lebar terisi.", "S13"),
        ("R&D (MD)", "SMP → [[Kirim ke supplier]] (pilih supplier peserta) → per supplier unggah bukti → [[Setor hasil]] → [[Nilai hasil]] (ACC/revisi/tolak)",
         "Hasil ukur per jenis uji (ΔE, tahan cuci/gosok; proofing), skor.", "Supplier yang lolos tertanda *ACC*.", "S13"),
        ("MD (atau Manajer)", "SMP → [[Pilih pemenang]] → supplier, **alasan keputusan**, **harga kesepakatan**, kode/nama/warna versi supplier → [[ACC & bentuk master data]] → [[Sample jadi]]",
         "Tombol nonaktif menyebut isian yang kurang (*Lengkapi: …*). Pemenang boleh diputus **MD atau Manajer**. "
         "Bila Manajer yang memutus: biarkan centang *ACC spesifikasi* agar SKU langsung lahir. MD tidak melihat centang itu — "
         "spesifikasi otomatis diajukan ke Manajer.",
         "Kontrak harga **KSC/SCT-…** terbit; nama barang & warna versi supplier tersimpan. Diputus MD → panel Master data: "
         "*Menunggu ACC spesifikasi oleh Manajer / Admin*.", "S13"),
        ("Manajer", "`Beranda` → **Spesifikasi produk menunggu ACC (SKU lahir)** (atau `Pusat Persetujuan` → [[Buka layarnya]]) → KSC/SPEC-… → [[Setujui & buat produk]]",
         "Hanya bila pemenang diputus MD. Pembuat spesifikasi = Sales pembuat OD, jadi Manajer tidak terblokir pemisahan tugas.",
         "**SKU eksklusif pelanggan** lahir (*Disetujui · belum rilis*); artikel bersumber restock *Supplier*.", "S13"),
        ("Sales", "HP: **Lainnya** › **Pesanan Khusus (OD)** → ketuk OD → **Persetujuan pelanggan atas sample** → [[ACC]] → kontak, catatan, foto bukti → [[Simpan keputusan]]",
         "Tanggal keputusan bawaan = hari ini (WIB). Alternatif desktop: `Meja Admin Sales` → *Pesanan khusus — menunggu ACC pelanggan* → [[Catat ACC]].",
         "*Keputusan pelanggan tersimpan*; riwayat ACC + bukti; OD masuk antrean kunci harga.", "S13"),
        ("Admin Sales", "`Meja Admin Sales` → **Pesanan khusus — perlu kunci harga** → [[Kunci harga]] → panel **Harga final & confirmed** → gudang tujuan *WH-JKT · Jakarta · Gudang Sukacita* → [[Kunci harga & Confirm OD]]",
         "Per item: SKU hasil · harga kontrak supplier pemenang · margin (bawaan 30%) · harga final. Item belum siap menyebut sebabnya (mis. *produk hasil sample … belum lahir*). "
         "Daftar gudang hanya yang aktif, gudang milik PT di atas; pilihan disimpan untuk realisasi.",
         "Notifikasi *Harga dikunci*; total OD = jumlah per item (contoh Rp 19.500.000 + PPN). SKU baru → panel pengadaan: "
         "*menunggu Manajer: rilis SKU baru ke produksi & realisasi pengadaan* (bukan galat).", "S13"),
        ("MD", "`Meja MD` → **Pesanan khusus — pilih jalur & realisasi pengadaan** → [[Buka]] → panel **Pemenuhan produksi per item** → jalur *Supplier (PR → PO)* → [[Simpan jalur]] (tiap item)",
         "Jalur bawaan mengikuti sumber restock artikel (sudah terisi bila master diatur) — simpan hanya bila menyimpang (alasan wajib).", "Item *Siap direalisasi*.", "S13"),
        ("Manajer", "detail OD → panel **Pemenuhan produksi per item** → [[Rilis SKU & realisasi pengadaan]] (tiap item)",
         "SKU baru dirilis ke produksi saat realisasi — wewenang Manajer (peran lain melihat *realisasi oleh Manajer*, tanpa tombol).",
         "Per item **PR-xxxxx → PO KSC/PO-xxxxx** ke supplier pemenang (*Belum diterima*); OD *Dalam Produksi*.", "S13"),
        ("Admin Sales", "detail OD → [[Ubah ke Pesanan Penjualan]] → [[Konversi ke SO]]",
         "Konversi item A & B (SKU, unit, harga terkunci); boleh sebelum barang datang.",
         "**KSC/SO-xxxxx** *Menunggu stok* (backorder per item) tertaut OD; ulang tidak membuat SO kedua.", "S13"),
        ("Admin Gudang · Gudang · MD Quality", "tiap PO → `Barang Masuk` kedatangan (Jakarta) → hitung → tutup → SPK MD → MDQ → [[Tutup SPK]] *Diterima seluruhnya*",
         "Sama dengan S8 bagian kedatangan & SPK (SPK MD Quality saja; QC 4-point opsional lewat SPK QC 4-point); PO item A dan B "
         "boleh tiba di hari berbeda.",
         "Roll item OD **berkomitmen** ke SO OD; SO **Terkonfirmasi otomatis** (*barang pesanan khusus diterima gudang*); OD *Siap* "
         "baru setelah **semua** PO item diterima; "
         "tugas ambil lahir **per item** di `Barang Keluar` (*Siap diambil*) — tanpa langkah Periksa & lepas Admin Sales.", ""),
    ] + s.pick("=S1") + s.dispatch("=S3") + s.logistics("ekspedisi", "=S1") +         s.pay("=S1") + s.journey("=S1", "OD ikut *Dikirim* lalu *Selesai* (sinkron dari SO).")


def _retur_front(ui="S14"):
    return [
        ("Sales", "HP: tab **Pesanan** → ketuk SO yang sudah Selesai (mis. dari S1) → [[Ajukan retur]] (atau **Lainnya** › **Retur Penjualan** → [[Buat retur jual]])",
         "SO terisi otomatis; roll yang benar-benar terkirim tampil. Pilih **Tipe Return**, centang roll (qty terisi) → **per roll**: alasan, "
         "kondisi, *hangtag hilang* / *sudah dipotong pelanggan*, foto per roll; **Sebab keluhan**, catatan → [[Buat Return]].",
         "**SRET-xxxxx** *Menunggu persetujuan*. Klaim > 21 hari dari SJ → ditolak / [[Ajukan pengecualian]].", ui),
        ("Manajer / Admin Sales", "`Retur` → baris retur [[Detail →]] → tab **Ringkasan** → tabel roll → per roll [[Terima]] / [[Tolak]] (+ alasan) → [[Simpan keputusan roll]]",
         "Penerimaan sebagian: roll yang tidak layak (mis. sudah dipotong) ditolak per roll. Pemutus bawaan Manajer & Admin Sales (bisa diatur di Hak Akses).",
         "Roll ditolak keluar dari klaim; qty & nilai retur menyesuaikan.", ui),
        ("Manajer", "`Meja Saya` → **Retur menunggu ACC** → [[Putuskan]] (membuka Inbox Persetujuan) → kartu retur [[Tinjau & Putuskan]] → [[Setujui]]",
         "Estimasi nilai dari harga SO; setujui barang kembali untuk diperiksa (bukan keputusan refund/tukar).",
         "Retur *Disetujui*; **SPK QC retur KSC/INS-…** (satu baris per roll) terbit otomatis — panel *QC retur · SPK inspeksi per roll*.", ui),
        ("Sales / Admin Sales", "detail retur → tab **Logistik & perjalanan** → panel **Pengembalian barang** → cara kembali (*Dijemput armada KN* / "
         "*Dikirim pelanggan via ekspedisi* + ekspedisi & resi / *Diantar sendiri*) → [[Barang sudah dikirim/dijemput]]",
         "Bisa [[Simpan rencana]] dulu (jadwal jemput) lalu ditandai saat barang berangkat.",
         "Stepper tahap 3 *Pengembalian barang*; tonggak *Barang dikirim/dijemput dari pelanggan*.", ui),
        ("Gudang", "`Retur` → baris retur [[Detail →]] → tab **Logistik & perjalanan** → **Perjalanan Retur** → tahap *Terima di gudang* → gudang *Jakarta* → ketik nomor roll → [[Catat scan]]",
         "Terima roll retur di Jakarta (scan barcode atau ketik nomor roll — tanpa RFID).",
         "Lokasi fisik roll: *Jakarta · Gudang Sukacita · SRET-…/TRM-1*; belum jadi stok jual.", ui),
        ("Gudang", "Perjalanan Retur → tahap **Kirim ke gudang lain (dalam perjalanan)** → tujuan *Rancamalang · Gudang Transit* → roll → ekspedisi/sopir → [[Catat scan]]",
         "Gudang asal tidak ada di daftar tujuan.", "Status *Dalam perjalanan Jakarta → Rancamalang · Gudang Transit*.", ui),
        (WH_RCM, "detail retur → Perjalanan Retur (tahap *Tiba di gudang tujuan* & gudang Transit terisi otomatis) → ketik roll → [[Catat scan]]",
         "Cocokkan roll.", "Roll di *Rancamalang · Gudang Transit* menunggu QC.", ui),
        ("QC", "`Kualitas` › **SPK Inspeksi** → SPK retur KSC/INS-… (atau detail retur → [[Buka SPK]]) → per roll [[Isi hasil]] → kondisi, **qty aktual**, cacat 4-point, **grade** → simpan → [[Tutup SPK]]",
         "Klaim pelanggan per roll tampil di atas form (alasan, kondisi, foto). Roll yang belum diterima gudang belum bisa diperiksa.",
         "Retur *Selesai Inspeksi*; hasil per roll (grade, cacat, qty aktual) tersalin ke retur. QC sebelum barang diterima → ditolak (F-12).", ui),
    ]


def _s14():
    return _retur_front("S14") + [
        ("MD Quality", "detail retur → panel **Cutloss & diskon** → catat cutloss (opsional)",
         "Catat qty cacat (yard) + posisi; pecah roll: potongan baik dikirim kembali, potongan cacat → BS / dibuang.",
         "Roll anak berurutan; potongan BS tercatat.", ""),
        ("Finance", "`Meja Finance` → **Retur selesai QC — putuskan nilai** → [[Putuskan]] → panel **Cutloss & diskon** → qty cacat "
         "(nominal terisi = harga transaksi × qty, bisa diubah) → **Catatan keputusan Finance (wajib)** → [[Putuskan nilai]]",
         "Harga transaksi per item tampil di panel.", "*Diputus Finance: Rp … · nama*; dasar hitung terlihat.", "S14"),
        ("Manajer", "detail retur → [[Selesaikan (Pilih Outcome)]] → **Nego (Diskon)** → kompensasi: *Jadi saldo* / *Refund tunai* / *Kurangi piutang SO asal* → bukti keputusan → [[Selesaikan (Nego (Diskon))]]",
         "Isi bukti keputusan (mis. *ACC Pak Budi via WA*). Pengembalian Dana / Store Credit dipakai bila barang kembali jadi stok.",
         "Retur *Nego*; **Nota Kredit CN-xxxxx** (diskon + PPN); saldo pelanggan bertambah. Admin Sales tidak bisa (403).", "S14"),
        ("Finance", "`Keuangan › Saldo Kredit` / `Meja Finance`",
         "SO asal belum lunas → potong tagihan dulu; sudah lunas → saldo / refund sesuai pilihan pelanggan.",
         "Saldo pelanggan & piutang benar; satu posting.", ""),
        ("Admin Sales", "detail retur (outcome Pengembalian Dana / Store Credit) → **Tujuan barang retur** → per roll [[Simpan sebagai stok]] / kembalikan ke PT pemasok",
         "Putuskan nasib roll hasil QC (outcome Nego: barang tetap milik pelanggan, tidak ada tujuan stok).",
         "Roll tersimpan dengan grade/hold hasil QC (bukan otomatis tersedia).", ""),
    ]


def _s15():
    return _retur_front("=S14") + [
        ("Manajer", "detail retur → [[Selesaikan (Pilih Outcome)]] → **Store Credit** (terpilih otomatis untuk tipe *Penggantian*) → bukti keputusan → [[Selesaikan (Store Credit)]]",
         "Petunjuk: nilai retur jadi saldo untuk pesanan pengganti.", "Retur *Store Credit*; roll retur *karantina*.", "S15"),
        ("Admin Sales", "`Meja Admin Sales` → **Retur tukar — buat pesanan pengganti** → [[Buat pengganti]] → panel **Pesanan pengganti** → [[Buat pesanan pengganti]]",
         "Artikel/warna/grade sama; qty = yard aktual hasil QC; harga transaksi asal. SO asal tunai → pengganti termin **CBD** "
         "(saldo retur melunasi di muka); SO asal ambil sendiri → tanggal ambil besok.",
         "**SO pengganti** tertaut retur: *saldo retur dipakai Rp … · ditagih Rp 0*; roll yang diretur tidak dialokasikan lagi.", "S15"),
    ] + s.release() + s.pick("=S6") + s.dispatch("=S3") + s.logistics("ekspedisi", "=S1") + \
        s.journey("=S1", "SO pengganti selesai; selisih nilai (bila ada) tertagih / dikembalikan.")


def _s16():
    return [
        ("Pembelian", "`Pembelian › Pengadaan › Saran Reorder` → centang artikel → isi **Saran Qty** → [[Buat PR dari Pilihan]]",
         "Restock artikel di bawah titik pesan ulang. Produk lama tanpa template artikel → PR tetap dibuat dengan peringatan.",
         "*PR-xxxxx dibuat … Lihat di tab Permintaan Pembelian* (≥ Rp50 jt → *Menunggu Persetujuan*).", "S16"),
        (("Admin", "admin@kainnusantara.id"), "`Pembelian › Pengadaan › Permintaan Pembelian` → PR → [[Setujui]] (bila di atas ambang)",
         "**Pemisahan tugas**: pembuat PR (Manajer) tidak boleh menyetujui PR-nya sendiri → ACC oleh Admin.", "PR *Disetujui*.", "S16"),
        ("Pembelian", "PR → [[Realisasi ke PO]] → supplier, gudang → [[Buat PO]]",
         "Supplier, gudang penerimaan, tanggal kirim.", "**PO KSC/PO-xxxxx** (≥ Rp100 jt → ACC Admin dulu).", "=S8"),
        ("Supplier", "di luar sistem", "Barang + SJ supplier (mis. 10 roll, SJ 1.000 yd, fisik 960 yd).", "—", ""),
        ("Admin Gudang", "`Operasi Gudang › Barang Masuk` → [[Kedatangan baru]] → SJ manual → target PO",
         "Isi kepala SJ & baris (1.000 yd, 10 roll); pilih Target dulu agar kode/deskripsi/satuan/PO terisi.", "GRN *Draf → Tinjau SJ*.", ""),
        ("Gudang", "[[Mulai hitung fisik]] per roll → [[Selesai hitung]]", "Catat fisik (10 × 96 = 960 yd).", "Roll *receiving*.", "=S8"),
        ("Admin Gudang", "**Rekonsiliasi** → selisih −40 yd (*Kurang dari SJ · pemblokir*) → [[Terima dengan catatan]] + alasan → [[Tutup Penerimaan]]",
         "Atau [[Klaim ke supplier]].",
         "Stok +960 yd; *tugas sisa 40 dibuat* (PO tetap *incoming* 40); roll karantina + SPK.", "S16"),
        ("Admin Gudang · MD Quality", "`Meja Gudang` → [[Tugaskan]] SPK MD → MD Quality → [[Tutup SPK]]",
         "Sama dengan S8 (SPK MD Quality saja).", "Roll tersedia.", ""),
        QC4(),
    ] + AP_STEPS("Selisih SJ vs fisik: tagihan = 960 yd.", ui="=S8")


# kode, judul, kapan terjadi, kelompok, mulai, menit, peran, data, perbaikan, status cek UI, langkah
SCENARIOS = [
    ("S1", "Penjualan biasa · stok ada · kirim ekspedisi · NET 30 → lunas",
     "Pesanan paling umum: stok PT sendiri cukup, dikirim lewat ekspedisi, pelanggan minta Faktur Pajak, bayar tempo 30 hari.",
     1, "09.15", 45, "Sales · Admin Sales · Gudang · Admin Gudang · Finance", "Toko Kain Sejahtera · CERUTY PREMIUM (yard)",
     "F-01 F-03 F-05 F-06 F-07 F-08 F-16 · E1 E2 E8 B6", "partial", _s1),
    ("S2", "Termin CBD (bayar sebelum kirim) · armada sendiri → lunas",
     "Pelanggan wajib bayar penuh sebelum barang keluar. Gudang boleh menyiapkan, tetapi kirim terkunci sampai Finance mencatat pembayaran.",
     1, "10.00", 35, "Sales · Admin Sales · Gudang · Finance · Admin Gudang", "Toko Kain Sejahtera · termin CBD",
     "F-10 · E8", "partial", _s2),
    ("S3", "Ambil sendiri di gudang · bayar tunai",
     "Pelanggan mengambil barang sendiri pada tanggal ambil; serah terima memakai kode pickup.",
     1, "10.35", 30, "Sales · Admin Sales · Gudang · Admin Gudang · Finance", "Toko Kain Sejahtera · termin Tunai",
     "E8", "partial", _s3),
    ("S4", "Harga khusus dari checkout ditolak → diajukan ulang → disetujui",
     "Pelanggan menawar di bawah harga saat checkout (harga khusus hanya untuk pesanan ini). Manajer menolak pengajuan pertama, "
     "Sales nego ulang, pengajuan kedua disetujui; pesanan yang sudah diperiksa Admin Sales dilepas ke gudang otomatis.",
     1, "11.05", 40, "Sales · Admin Sales · Manajer · Gudang · Admin Gudang · Finance", "Toko Kain Sejahtera",
     "F-09 · E8 E10", "partial", _s4),
    ("S5", "Kredit melewati limit → izin kredit Manajer → SO",
     "Nilai pesanan membuat piutang pelanggan melewati limit kredit: checkout terkunci (SO tidak lahir) sampai Manajer menyetujui "
     "izin kredit yang diajukan Sales dari HP.",
     1, "11.45", 35, "Sales (Kanda) · Admin Sales (Kanda) · Manajer · Gudang Soreang · Admin Gudang · Finance",
     "CV Garmen Soreang Jaya (limit Rp25 jt) · LYFLEX ACTIVE BEIGE (kg)", "F-09 · E2 E3 E8", "partial", _s5),
    ("S6", "Pelanggan minta QC sebelum kirim",
     "Barang wajib lulus QC per roll sebelum boleh dikirim.",
     1, "13.20", 40, "Sales · Admin Sales · Gudang · Admin Gudang · QC · Finance", "Toko Kain Sejahtera",
     "F-14 · E8 F1 F5", "partial", _s6),
    ("S7", "Stok kurang → dipenuhi dari PT lain (antar-PT)",
     "Stok Sukacita tidak cukup; kekurangan diambil dari Cipta Sandang lewat transaksi antar-PT.",
     1, "14.00", 50, "Sales · Admin Sales · CST · Gudang Rancamalang · Admin Gudang · Finance", "ALICE KNIT 14 A (kg, stok CST)",
     "F-05 · E5 E8", "partial", _s7),
    ("S14", "Retur → kompensasi (refund / saldo / nego)",
     "Pelanggan komplain barang; setelah diterima & di-QC, diselesaikan dengan uang kembali, saldo, atau diskon.",
     1, "15.05", 45, "Sales · Manajer · Gudang Jakarta & Rancamalang · QC · MD Quality · Finance · Admin Sales", "SO dari S1 (sudah Selesai)",
     "F-11 F-12 F-17", "full", _s14),
    ("S15", "Retur → barang pengganti",
     "Komplain diselesaikan dengan mengirim barang pengganti sampai diterima.",
     1, "15.50", 40, "Sales · Manajer · Gudang · QC · Admin Sales · Admin Gudang", "SO dari S1",
     "F-11 F-12 · E8", "partial", _s15),
    ("S8", "Stok kurang → PO supplier → kedatangan → SPK → kirim",
     "Kekurangan dibeli dari supplier; barang datang, dihitung, diinspeksi, lalu otomatis dicadangkan ke SO.",
     2, "09.15", 75, "Sales · Admin Sales · Pembelian · Admin Gudang · Gudang · MD Quality · QC · Finance", "ALICE KNIT 14 A · supplier dari master",
     "F-13 F-14 · B3 D2 E8 E9 F5", "partial", _s8),
    ("S9", "Stok kurang → makloon (proses di mitra)",
     "Barang jadi dibuat dari bahan sendiri oleh mitra makloon, lalu diterima & dikirim ke pelanggan.",
     2, "10.30", 60, "Sales · Admin Sales · Pembelian · Gudang · Admin Gudang · QC · Finance", "RIVERA RIB BW A · resep celup · PT Celup Warna Dayeuhkolot",
     "F-13 F-14 · E8", "partial", _s9),
    ("S10", "Multi-gudang Rancamalang → transit → pelanggan Jakarta",
     "Satu pesanan PT Cipta Sandang dari beberapa gudang Rancamalang dikumpulkan di Gudang Transit lewat transfer pemenuhan SO, lalu dikirim ke pelanggan di Jakarta.",
     2, "11.30", 40, "Sales CST · Admin Sales CST · Gudang Rancamalang · Admin Gudang CST · Finance", "SHAKILA LAK (Woven) + ALICE KNIT 8 A (Knitting) · CST",
     "F-05 · E8 F1", "partial", _s10),
    ("S11", "Sample gratis",
     "Pelanggan minta potongan contoh tanpa biaya.",
     2, "13.20", 25, "Sales · Admin Sample · Gudang · Admin Gudang", "Toko Kain Sejahtera", "F-03 · A2 F1 F2", "partial", lambda: _sample(False)),
    ("S12", "Sample berbayar",
     "Potongan contoh dibayar pelanggan; harga mengikuti panjang aktual (persetujuan ulang bila berubah > ±5%).",
     2, "13.45", 35, "Sales · Finance · Admin Sample · Gudang · Admin Gudang", "Toko Kain Sejahtera", "F-15 · A2 F1 F2", "partial", lambda: _sample(True)),
    ("S13", "Pesanan Khusus (desain/warna baru) → SO → lunas",
     "Produk belum ada: desain, sample R&D, ACC pelanggan, kunci harga, pengadaan, lalu menjadi SO biasa sampai lunas.",
     2, "14.20", 75, "Sales · Manajer · MD · Desainer · Admin Sales · Gudang · QC · Finance", "OD 2 item (A 100 m, B 200 m)",
     "E9", "partial", _s13),
    ("S16", "Pembelian stok (restock) → hutang supplier lunas",
     "Restock rutin dari saran reorder sampai tagihan supplier dibayar; selisih SJ vs fisik diputuskan.",
     2, "15.35", 45, "Pembelian (Manajer) · Admin · Admin Gudang · Gudang · MD Quality · QC", "Saran Reorder · SJ 1.000 yd vs fisik 960 yd",
     "F-14 · B3 E9 F5", "partial", _s16),
]
