"""FASE G-0 — Katalog registry konfigurasi: aturan bisnis LINTAS MODUL (scope `global`).

Semua entri di sini tersimpan pada dokumen `system_settings{scope:"global"}` dan bisa
di-override per entitas (`system_settings{scope:"<entity_id>"}`) — sesuai kemampuan
`config_service.get_effective_settings()` yang sudah ada.

Gaya penulisan label/help/impact SENGAJA memakai bahasa awam (bukan istilah teknis)
karena inilah teks yang dibaca pemilik usaha di Pusat Pengaturan.
"""
from config_registry import E

RP = "Rp"

# ═══════════════════════════════════════════════════════════════════════════
# PAJAK
# ═══════════════════════════════════════════════════════════════════════════
# KP-T4 — alasan baku kunci persetujuan yang pindah ke Aturan Persetujuan.
_KPT4_TIDAK_DIPAKAI = ("Dipindah ke Aturan Persetujuan (Pengaturan › Persetujuan › Aturan Persetujuan). Nilai terakhirnya hanya membentuk aturan bawaan selama aturan belum disimpan.")

E("tax.ppn_rate", sensitif_baca=False,  # KF-T1 — dibaca layar semua pengguna
  group="pajak-pembukuan", section="pajak", type="pct", default=12.0, min=0, max=100, step=0.5,
  unit="%", scopes=("global", "entity"), simulate="tax",
  label="Tarif PPN",
  help="Tarif Pajak Pertambahan Nilai yang dipakai saat membuat tagihan penjualan. Isi 0 = tagihan tanpa PPN.",
  impact="Mengubah nilai PPN pada SEMUA tagihan baru. Tagihan yang sudah terbit tidak berubah.",
  example="Subtotal Rp 10.000.000 · tarif 12% + DPP Nilai Lain → PPN Rp 1.100.000",
  # TX-T1 — mesin membaca lewat `tax_settings` (tanggal dokumen, lapisan PT); `compute_tax` memakai hasilnya.
  consumers=("services/tax_config_service.py:tax_settings", "services/config_service.py:compute_tax",
             "services/tax_invoice_service.py"),
  related=("tax.dpp_nilai_lain", "tax.ppn_mode"), risk="high")

E("tax.dpp_nilai_lain", sensitif_baca=False,  # KF-T1 — dibaca layar semua pengguna
  group="pajak-pembukuan", section="pajak", type="bool", default=True,
  scopes=("global", "entity"), simulate="tax",
  label="Pakai DPP nilai lain",
  help="Aturan PMK 131/2024: dasar pengenaan pajak = pecahan × harga jual untuk barang non-mewah, sehingga PPN "
       "efektif tetap 11% walau tarif tertulis 12%. Pecahannya diatur di Faktor DPP nilai lain (bawaan 11/12).",
  impact="Nominal rupiah PPN turun ke setara 11%. Kolom DPP pada Faktur Pajak berubah.",
  example="Harga jual Rp 12.000.000 → DPP Rp 11.000.000 → PPN 12% × DPP = Rp 1.320.000",
  related=("tax.dpp_nilai_lain_pembilang", "tax.dpp_nilai_lain_penyebut"),
  consumers=("services/tax_config_service.py:tax_settings",), risk="high")

E("tax.ppn_mode", sensitif_baca=False,  # KF-T1 — dibaca layar semua pengguna
  group="pajak-pembukuan", section="pajak", type="enum", default="excluded",
  options=({"value": "excluded", "label": "Harga BELUM termasuk PPN (ditambah)"},
           {"value": "included", "label": "Harga SUDAH termasuk PPN (dipisah)"}),
  scopes=("global", "entity"), simulate="tax",
  label="Cara menghitung PPN dari harga",
  help="Menentukan apakah harga yang diketik sales sudah termasuk PPN. Bila sudah termasuk, sistem memisahkannya "
       "menjadi DPP + PPN; bila belum, PPN ditambahkan di atas harga.",
  impact="Mengubah total tagihan. 'Harga SUDAH termasuk PPN' membuat harga jual dipecah menjadi DPP + PPN.",
  example="Rp 11.100.000 · Harga SUDAH termasuk PPN → DPP Rp 10.000.000 + PPN Rp 1.100.000",
  consumers=("services/tax_config_service.py:tax_settings",), risk="high")

# KF-T3 (KF-11) — sakelar ini tidak pernah dibaca saat menghitung PPN maupun menerbitkan faktur; sumbernya status PKP
# di profil PT (keputusan K-08). Pusat Pajak kini mengirim `efaktur_enabled = is_pkp`.
E("tax.efaktur_enabled", group="pajak-pembukuan", section="pajak", type="bool", default=True,
  scopes=("global", "entity"),
  label="Terbitkan Faktur Pajak",
  help="Dulu menandai PT yang menerbitkan Faktur Pajak. Sekarang Faktur Pajak mengikuti status PKP di profil PT, "
       "jadi sakelar ini tidak dibaca. Besar PPN diatur di Tarif PPN.",
  impact="Tidak berpengaruh lagi: PT berstatus PKP menerbitkan Faktur Pajak, PT bukan PKP tidak.",
  example="PT non-PKP → PPN Rp 0 dan tidak ada nomor Faktur Pajak",
  consumers=("services/tax_center_service.py:tax_summary",),
  risk="high",
  status="not_used", not_used_reason="Penerbitan faktur pajak mengikuti status PKP di profil PT.")

E("tax.pph_items", group="pajak-pembukuan", section="pajak", type="table", default=[],
  scopes=("global", "entity"),
  row_shape="list",
  columns=({"name": "enabled", "label": "Aktif", "type": "bool", "default": True, "width": "60px"},
           {"name": "code", "label": "Kode", "type": "text", "default": "pph_baru", "width": "120px"},
           {"name": "name", "label": "Nama butir", "type": "text", "default": "Butir PPh Baru"},
           {"name": "basis", "label": "Dasar hitung", "type": "enum", "default": "manual",
            "options": [{"value": "payroll", "label": "Payroll (PPh21 otomatis/TER)"},
                        {"value": "omzet", "label": "Omzet (tarif × peredaran bruto)"},
                        {"value": "manual", "label": "Manual (rekam DPP)"}],
            "width": "220px"},
           {"name": "rate", "label": "Tarif", "type": "pct", "default": 0, "unit": "%",
            "width": "110px",
            "disabled_when": {"field": "basis", "equals": "payroll"},
            "hint": "Basis payroll memakai PPh 21 aktual (TER) — tarif diabaikan."}),
  label="Daftar PPh yang dipotong",
  help="Butir PPh yang berlaku untuk perusahaan (PPh 21 karyawan, PPh 23 jasa, PPh Final UMKM). "
       "Setiap butir punya tarif dan dasar hitung sendiri.",
  impact="Menentukan butir yang muncul di Pusat Pajak → PPh & Rekap serta nominal potongannya.",
  example="PPh 23 jasa 2% aktif → tagihan jasa makloon Rp 50.000.000 dipotong Rp 1.000.000",
  consumers=("services/tax_center_service.py",), risk="medium")

# TX-T1 (K-33, TX-06) — nilai yang dulu ditulis mati di kode (faktor 11/12 di empat tempat, pembulatan dua desimal,
# daftar & bawaan kode transaksi faktur) kini pengaturan per PT dengan NILAI YANG SAMA (H4: tidak ada tarif/faktor/kode
# baru). Dibaca `tax_config_service.tax_settings` pada tanggal dokumen; dokumen menyimpan potretnya (`tax_snapshot`).
# Hal peraturan (faktor, daftar kode) menunggu konfirmasi konsultan pajak.
_TXT1 = dict(group="pajak-pembukuan", section="pajak", scopes=("global", "entity"), risk="high",
             requires_reason=True, permission=("accounting", "manage"),
             consumers=("services/tax_config_service.py:tax_settings",))
#: Kode transaksi faktur yang dikenal sistem — sama persis dengan daftar yang dulu ditulis di
#: `tax_invoice_service.KODE_TRANSAKSI_VALID` (05 tidak ada di daftar lama, jadi tidak ditambahkan).
_KODE_TRANSAKSI = tuple({"value": k, "label": k} for k in ("01", "02", "03", "04", "06", "07", "08", "09"))

E("tax.dpp_nilai_lain_pembilang", sensitif_baca=False, **{**_TXT1, "consumers": (
      "services/tax_config_service.py:tax_settings", "utils/pricing.js")},
  type="int", default=11, min=1, max=1000, step=1, unit="bagian", simulate="tax",
  label="Faktor DPP nilai lain — pembilang",
  help="Bagian atas pecahan DPP nilai lain. Dipakai bila 'Pakai DPP nilai lain' menyala.",
  impact="Mengubah DPP dan PPN semua dokumen baru PT ini. Dokumen yang sudah dibuat tetap memakai aturan saat dibuat.",
  example="11 dari 11/12")

E("tax.dpp_nilai_lain_penyebut", sensitif_baca=False, **{**_TXT1, "consumers": (
      "services/tax_config_service.py:tax_settings", "utils/pricing.js")},
  type="int", default=12, min=1, max=1000, step=1, unit="bagian", simulate="tax",
  label="Faktor DPP nilai lain — penyebut",
  help="Bagian bawah pecahan DPP nilai lain. Dipakai bila 'Pakai DPP nilai lain' menyala.",
  impact="Mengubah DPP dan PPN semua dokumen baru PT ini. Dokumen yang sudah dibuat tetap memakai aturan saat dibuat.",
  example="Harga Rp 12.000.000 × 11/12 = DPP Rp 11.000.000")

E("tax.pembulatan_tingkat", sensitif_baca=False, **{**_TXT1, "consumers": (
      "services/tax_config_service.py:tax_settings", "utils/pricing.js")},
  type="enum", default="dokumen",
  options=({"value": "dokumen", "label": "Per dokumen (dari total)"},
           {"value": "baris", "label": "Per baris (tiap baris lalu dijumlah)"}),
  label="PPN dibulatkan per",
  help="Per dokumen = PPN dihitung dari total pesanan; per baris = PPN dihitung tiap baris lalu dijumlah.",
  impact="Bisa menggeser PPN beberapa rupiah pada dokumen baru. Dokumen yang sudah dibuat tidak berubah.",
  example="Dua baris Rp 100.005: per baris Rp 22.002, per dokumen Rp 22.001 (rupiah penuh)")

E("tax.pembulatan_satuan", sensitif_baca=False, **{**_TXT1, "consumers": (
      "services/tax_config_service.py:tax_settings", "utils/pricing.js")},
  type="enum", default="dua_desimal", simulate="tax",
  options=({"value": "dua_desimal", "label": "Dua angka di belakang koma"},
           {"value": "rupiah_penuh", "label": "Rupiah penuh"}),
  label="PPN dibulatkan ke",
  help="Ketelitian angka PPN, DPP, dan total pada dokumen baru.",
  impact="Mengubah angka PPN dan total dokumen baru. Dokumen yang sudah dibuat tidak berubah.",
  example="Rp 135.802,37 menjadi Rp 135.802")

E("tax.kode_transaksi_diizinkan", sensitif_baca=False, **_TXT1,
  type="list", items="options", options=_KODE_TRANSAKSI,
  default=[o["value"] for o in _KODE_TRANSAKSI],
  label="Kode transaksi faktur yang dipakai",
  help="Pilihan kode transaksi saat menerbitkan faktur pajak keluaran PT ini.",
  impact="Kode di luar daftar ditolak saat menerbitkan, mengganti, atau mengisi nomor seri faktur.",
  example="Hapus 07 → faktur berkode 07 ditolak")

E("tax.kode_transaksi_bawaan", sensitif_baca=False, **_TXT1,
  type="enum", default="01", options=_KODE_TRANSAKSI,
  label="Kode transaksi bawaan",
  help="Dipakai bila pelanggan tidak punya kode sendiri dan pesanan tidak memakai DPP nilai lain.",
  impact="Mengisi otomatis kode faktur pajak baru. Kode yang tidak ada di daftar kode PT ditolak saat terbit.",
  example="01")

E("tax.kode_transaksi_bawaan_dpp_nilai_lain", sensitif_baca=False, **_TXT1,
  type="enum", default="04", options=_KODE_TRANSAKSI,
  label="Kode transaksi bawaan saat DPP nilai lain",
  help="Dipakai bila pelanggan tidak punya kode sendiri dan pesanan memakai DPP nilai lain.",
  impact="Mengisi otomatis kode faktur pajak baru. Kode yang tidak ada di daftar kode PT ditolak saat terbit.",
  example="04")

# TX-T2 (K-32, TX-05) — kapan faktur pajak lahir. Bawaan `pesanan` = perilaku sebelum TX-T2 (diterbitkan orang untuk
# seluruh pesanan). `uang_muka` terdaftar (K-32) tetapi DITOLAK saat disimpan (`tax_config_service.periksa_pemicu_faktur`):
# jurnal PPN atas uang muka belum ditetapkan (H4, konfirmasi konsultan pajak). Mengubahnya untuk PT nyata = H5.
E("tax.pemicu_faktur", sensitif_baca=False, **{**_TXT1, "consumers": (
      "services/tax_invoice_service.py:draft_for_shipment", "services/tax_invoice_service.py:issue_tax_invoice")},
  type="enum", default="pesanan",
  options=({"value": "pesanan", "label": "Per pesanan"},
           {"value": "surat_jalan", "label": "Per surat jalan"},
           {"value": "uang_muka", "label": "Per uang muka (belum bisa dipakai)"}),
  label="Faktur pajak dibuat saat",
  help=("'Per pesanan' = diterbitkan orang untuk seluruh pesanan, seperti sekarang. 'Per surat jalan' = draf muncul "
        "sendiri tiap barang keluar."),
  impact=("Mengubah kapan dan berapa banyak faktur per pesanan. Pesanan yang sudah berfaktur per pesanan tidak diberi "
          "draf per surat jalan."),
  example="Per surat jalan · pesanan dikirim dua kali → dua draf faktur")

# ═══════════════════════════════════════════════════════════════════════════
# DASAR KEUANGAN & PERIODE
# ═══════════════════════════════════════════════════════════════════════════
E("finance.base_currency", group="pajak-pembukuan", section="tutup-buku", type="enum", default="IDR",
  options=({"value": "IDR", "label": "Rupiah (IDR)"},
           {"value": "USD", "label": "Dolar AS (USD)"}),
  scopes=("global", "entity"), simulate="currency",
  label="Mata uang pembukuan",
  help="Mata uang yang dipakai seluruh laporan keuangan dan dokumen cetak.",
  impact="Mengubah simbol & format angka pada laporan, PDF tagihan, dan surat jalan.",
  example="IDR → 'Rp 1.250.000' · USD → '$ 1,250.00'",
  consumers=("services/config_currency.py:money_format", "services/pdf_service.py",
             "services/pdf_engine.py:fmt_rp"),
  risk="medium")

E("finance.fiscal_year_end_month", group="pajak-pembukuan", section="tutup-buku", type="int", default=12,
  min=1, max=12, step=1, unit="bulan", scopes=("global", "entity"), simulate="fiscal_year",
  label="Bulan tutup tahun buku",
  help="Bulan terakhir tahun buku. 12 berarti tahun buku Januari–Desember.",
  impact="Menentukan periode tahun fiskal pada laporan keuangan dan proses tutup buku tahunan.",
  example="Diisi 3 → tahun buku April 2026 s/d Maret 2027",
  consumers=("services/config_currency.py:fiscal_year_of",
             "services/closing_service.py:period_bounds"),
  risk="high")

E("finance.default_payment_term_code", sensitif_baca=False,  # KF-T1 — dibaca layar semua pengguna
  group="pembayaran-pelanggan", section="syarat-bayar", type="text", default="NET30",
  scopes=("global", "entity"),
  label="Syarat bayar bawaan pesanan baru",
  help="Syarat bayar yang otomatis terpilih saat membuat pesanan bila pelanggan belum punya syarat bayar sendiri. "
       "Pilih dari daftar Syarat Bayar, mis. NET30 = tempo 30 hari.",
  impact="Mengubah tanggal jatuh tempo bawaan pada pesanan & tagihan baru.",
  example="NET30 → tagihan tanggal 1 Juli jatuh tempo 31 Juli",
  # KF-T3 (KP-11) — pembaca nyata: termin bawaan PT pesanan; `ar_aging_service.py` tidak membacanya.
  consumers=("services/config_service.py:default_payment_term_code", "routers/sales_orders.py:create_order"),
  risk="medium",
  ref="payment_term")

E("finance.dispatch_payment_gate", group="pembayaran-pelanggan", section="syarat-bayar", type="enum", default="block",
  options=({"value": "block", "label": "Tahan kirim sampai dibayar"},
           {"value": "off", "label": "Tidak menahan (hanya peringatan)"}),
  scopes=("global", "entity"),
  label="Tahan kirim sampai CBD/DP dibayar",
  help="Pesanan dengan syarat bayar CBD atau DP tidak bisa dikirim sebelum pembayarannya mencapai persen yang "
       "disyaratkan. Pengecualian per pesanan hanya oleh pemegang izin khusus, dengan alasan tertulis.",
  impact="Bila 'Tahan kirim sampai dibayar', tombol Kirim di Barang Keluar, maju tahap gudang, dan cek "
         "keberangkatan trip menolak pesanan yang belum dibayar sesuai syarat bayar. Persen per syarat bayar diatur "
         "di Syarat Bayar.",
  example="Pesanan CBD Rp 10.000.000 baru dibayar Rp 4.000.000 → tertahan (kurang Rp 6.000.000)",
  consumers=("services/dispatch_payment_gate.py:evaluate", "services/loading_check_service.py:dispatch_guard"),
  risk="high")

# UAT v3 (2026-10-22) — gudang tanpa perangkat RFID (UAT / pelatihan) tetap bisa menjalankan alur kirim penuh.
E("wms.rfid_simulation", group="sistem", section="rfid-proses", type="bool", default=False,
  scopes=("global", "entity"),
  label="Mode latihan RFID (tanpa alat)",
  help="Untuk uji coba atau pelatihan tanpa printer tag dan alat baca: petugas bisa membuat tag pura-pura dan scan "
       "pura-pura dianggap sah. Matikan saat operasional nyata.",
  impact="Bila aktif, kirim tidak lagi tertahan 'roll belum bertag RFID aktif' — Staf Gudang bisa membuat tag simulasi "
         "sendiri. MATIKAN di operasional nyata.",
  example="UAT: roll RL-18027 belum bertag → [Buat tag simulasi] → tag aktif (simulasi) → Kirim Semua berhasil",
  consumers=("services/loading_check_service.py:simulation_on",), risk="high")

# ═══════════════════════════════════════════════════════════════════════════
# UANG MASUK & PIUTANG (AR)
# ═══════════════════════════════════════════════════════════════════════════
E("ar.denda_rate_pct_per_month", group="pembayaran-pelanggan", section="denda", type="pct", default=2.0,
  min=0, max=100, step=0.25, unit="% / bulan",
  scopes=("global", "entity"), simulate="ar_penalty",
  label="Bunga denda keterlambatan",
  # CR-T4 — lapisan pelanggan dicabut: tarif khusus satu pelanggan diatur di profil kreditnya (kartu pelanggan › Kredit).
  help="Persen denda per bulan atas tagihan yang lewat jatuh tempo, dihitung harian (30 hari = 1 bulan). Isi 0 = "
       "tidak ada denda. Untuk pelanggan tertentu, atur di kartu pelanggan (Aturan denda).",
  impact="Mengubah nota denda dan kolom 'Denda' pada laporan Umur Piutang.",
  example="Outstanding Rp 10.000.000 · telat 45 hari · 2%/bulan → denda Rp 300.000",
  consumers=("services/penalty_service.py:penalty_policy", "services/ar_aging_service.py:get_ar_config"),
  related=("ar.grace_days",), risk="medium")

E("ar.grace_days", group="pembayaran-pelanggan", section="denda", type="duration", default=0, min=0, max=180, step=1,
  unit="hari", scopes=("global", "entity"), simulate="ar_penalty",
  label="Masa tenggang sebelum denda",
  help="Jumlah hari setelah jatuh tempo yang masih bebas denda. Untuk pelanggan tertentu, atur di kartu pelanggan "
       "(Aturan denda). Isi 0 = denda dihitung sejak hari pertama lewat jatuh tempo.",  # KF-T5, CR-T4
  impact="Hari keterlambatan dikurangi masa tenggang sebelum denda dihitung.",
  example="Tenggang 7 hari · telat 10 hari → denda hanya dihitung 3 hari",
  consumers=("services/penalty_service.py:penalty_policy", "services/ar_aging_service.py:get_ar_config"),
  related=("ar.denda_rate_pct_per_month",), risk="low")

E("ar.aging_buckets", group="pembayaran-pelanggan", section="syarat-bayar", type="list", default=[30, 60, 90],
  scopes=("global", "entity"), simulate="ar_bucket",
  label="Kelompok umur piutang (hari)",
  help="Batas hari tiap kolom laporan Umur Piutang. Ketik dipisah koma: 30, 60, 90 berarti kolom 1–30, 31–60, "
       "61–90, dan di atas 90 hari.",
  impact="Mengubah kolom laporan Umur Piutang serta definisi 'pelanggan bermasalah'.",
  example="14, 30, 60 → kolom 1–14, 15–30, 31–60, di atas 60 hari",
  consumers=("services/ar_aging_service.py:_bucket",), risk="medium",
  items="int_asc")

# ═══════════════════════════════════════════════════════════════════════════
# HARGA, DISKON & KOMISI
# ═══════════════════════════════════════════════════════════════════════════
E("sales.allow_item_discount", sensitif_baca=False,  # KF-T1 — dibaca layar semua pengguna
  group="penjualan", section="harga", type="bool", default=False,
  scopes=("global", "entity"), simulate="pricing",
  label="Izinkan diskon per baris (penjualan)",
  help="Bila mati, sales tidak bisa mengetik diskon di baris pesanan; potongan harga hanya lewat Harga Khusus yang "
       "disetujui.",
  impact="Kolom diskon di layar pesanan hilang dan diskon selalu dihitung 0%.",
  example="Mati → baris Rp 10.000.000 diskon 5% tetap dihitung Rp 10.000.000",
  consumers=("services/config_service.py:compute_order_pricing", "utils/pricing.js"),
  related=("sales.allow_order_discount",), risk="medium")

E("sales.allow_order_discount", sensitif_baca=False,  # KF-T1 — dibaca layar semua pengguna
  group="penjualan", section="harga", type="bool", default=False,
  scopes=("global", "entity"), simulate="pricing",
  label="Izinkan diskon total pesanan (penjualan)",
  help="Mengizinkan satu potongan untuk seluruh pesanan, di luar diskon per baris. Bila mati, potongan itu tidak "
       "dihitung.",
  impact="Menentukan apakah field diskon order dipakai saat menghitung DPP dan PPN.",
  example="Aktif · diskon order 2% dari Rp 20.000.000 → potongan Rp 400.000",
  consumers=("services/config_service.py:compute_order_pricing", "utils/pricing.js"),
  risk="medium")

E("sales.keep_max_age_days", group="penjualan", section="alur-pesanan", type="int", default=0,
  scopes=("global", "entity"),
  label="Batas hari pesanan menunggu verifikasi",
  help="Pesanan yang belum diverifikasi Admin Sales lebih lama dari sekian hari ditandai merah “lewat batas”. Isi 0 "
       "bila tanpa batas; tidak membatalkan pesanan dan tidak mengubah stok.",
  impact="Daftar Keep di Meja Admin Sales menandai SO yang lewat batas dan menghitungnya terpisah.",
  example="3 → SO yang dibuat 4 hari lalu dan belum diverifikasi tampil merah 'lewat batas'",
  consumers=("services/sales_p04_service.py:keep_limit_days",), risk="low",
  unit="hari")
E("sales.sample_payment_tolerance_pct", group="penjualan", section="harga", type="pct", default=5.0, min=0, max=100, step=0.5,
  unit="%", scopes=("global", "entity"),
  label="Toleransi selisih tagihan sample berbayar",
  help="Bila sample berbayar dipotong dengan panjang berbeda dari yang disetujui, selisih tagihan sampai persen ini "
       "disesuaikan otomatis; di atasnya perlu persetujuan ulang dan kiriman sample ditahan. Isi 0 = setiap selisih "
       "perlu persetujuan ulang.",
  impact="Menentukan kapan potong sample memicu persetujuan ulang pembayaran (Meja Admin Sample).",
  example="Disetujui Rp 83.250, dipotong 3,1 yd → Rp 86.025 (+3,3%) ≤ 5% → disesuaikan otomatis",
  consumers=("services/sample_sale_service.py:payment_after_reprice",), risk="medium")
E("sales.allow_partial_shipment", group="penjualan", section="alur-pesanan", type="bool", default=True,
  scopes=("global", "entity"),
  label="Izinkan kirim sebagian",
  help="Bila aktif, pesanan boleh dikirim bertahap saat stok belum lengkap. Bila mati, "
       "pesanan dipaksa berkebijakan kirim penuh (tunggu stok lengkap).",
  impact="Menentukan kebijakan pengiriman yang tersimpan pada pesanan baru dan pembentukan backorder.",
  example="Aktif → pesanan 1.000 yard boleh dikirim 600 dulu, sisanya menyusul",
  consumers=("routers/sales_orders.py:create_order",), risk="medium")

E("sales.quotation_enabled", group="penjualan", section="alur-pesanan", type="bool", default=False,
  scopes=("global", "entity"), status="not_used",
  not_used_reason=("Alur Penawaran (Quotation) BELUM ADA di sistem — tidak ada satu pun "
                   "endpoint atau layar penawaran. Mengubah tombol ini TIDAK berpengaruh. "
                   "Ditandai jujur di sini (bukan disembunyikan) dan masuk daftar pekerjaan "
                   "FASE G lanjutan. Sementara ini: sales membuat Pesanan langsung, dan "
                   "potongan harga ditempuh lewat 'Ajukan Harga Khusus'."),
  label="Aktifkan Penawaran (Quotation)",
  help="Bila alur Penawaran dibangun, sales membuat Penawaran lebih dulu sebelum pesanan resmi.",
  impact=("BELUM ADA DAMPAK — fitur Penawaran belum dibangun sehingga pengaturan ini tidak dibaca mesin mana pun."),
  example="— (menunggu fitur Penawaran dibangun)")

# ── F1b (D-14) — Penjagaan harga langganan per pelanggan ────────────────────
# Keputusan pemilik 2026-08-10: harga khusus pelanggan yang jatuh di bawah harga PT
# atau di bawah biaya pokok WAJIB lewat persetujuan manajer, dan memakai MESIN
# persetujuan yang sudah ada (Harga Khusus / `price_approvals`) — bukan alur baru.
E("pricelist.customer_price_approval", group="penjualan", section="harga", type="bool", default=True,
  scopes=("global", "entity"),
  label="Harga di bawah batas wajib disetujui",
  help="Bila aktif, harga langganan pelanggan yang lebih rendah dari batas bawah tidak langsung berlaku; harus "
       "disetujui dulu.",
  impact="Menentukan apakah record harga pelanggan baru berstatus 'menunggu persetujuan' "
         "atau langsung berlaku pada pesanan & POS.",
  example="Batas Rp 150.000 · admin menetapkan Rp 120.000 → menunggu persetujuan manajer",
  consumers=("services/price_guard_service.py", "services/customer_price_service.py"),
  related=("pricelist.customer_price_floor", "pricelist.customer_price_tolerance_pct"),
  risk="high")

E("pricelist.customer_price_floor", group="penjualan", section="harga", type="enum", default="both",
  options=({"value": "entity_price", "label": "Harga jual PT"},
           {"value": "hpp", "label": "Biaya pokok (HPP)"},
           {"value": "both", "label": "Keduanya (pakai yang lebih tinggi)"}),
  scopes=("global", "entity"),
  label="Dasar batas bawah harga pelanggan",
  help="Angka pembanding untuk menilai harga “terlalu murah”: harga jual PT, biaya pokok barang, atau yang lebih "
       "tinggi dari keduanya.",
  impact="Mengubah kapan sebuah harga dianggap di bawah batas sehingga butuh persetujuan.",
  example="Pilihan 'Keduanya' · harga PT Rp 150.000 · HPP Rp 130.000 → batas Rp 150.000",
  consumers=("services/price_guard_service.py",),
  related=("pricelist.customer_price_approval",), risk="medium")

E("pricelist.customer_price_tolerance_pct", group="penjualan", section="harga", type="pct", default=0.0,
  min=0, max=100, step=1, unit="% di bawah batas", scopes=("global", "entity"),
  label="Toleransi di bawah batas tanpa persetujuan",
  help="Selisih kecil yang masih dimaafkan supaya pembulatan harga tidak memicu antrean "
       "persetujuan. 0% = sedikit pun di bawah batas sudah butuh persetujuan.",
  impact="Menaikkan angka ini memperlebar harga yang boleh berlaku tanpa persetujuan.",
  example="Batas Rp 150.000 · toleransi 2% → harga ≥ Rp 147.000 tetap langsung berlaku",
  consumers=("services/price_guard_service.py",),
  related=("pricelist.customer_price_approval",), risk="medium")

E("commission.strategy", group="penjualan", section="komisi", type="enum", default="per_sku",
  options=({"value": "per_sku", "label": "Per SKU (tarif per barang)"},
           {"value": "achievement_tiered", "label": "Berjenjang dari pencapaian target"}),
  scopes=("global", "entity"),
  label="Cara menghitung komisi sales",
  help="Per barang: tarif rupiah per satuan barang yang terjual. Berjenjang: persen dari pencapaian target.",
  impact="Mengubah seluruh perhitungan insentif sales pada periode berjalan.",
  example="Per barang · tarif Rp 500/yard · terjual 2.000 yard → komisi Rp 1.000.000",
  consumers=("services/sales_force_service.py", "routers/incentive_rates.py"), risk="high")

E("commission.incentive_unit", group="penjualan", section="komisi", type="text", default="meter",
  scopes=("global", "entity"),
  label="Satuan tarif komisi",
  help="Satuan yang dipakai saat menulis tarif komisi rupiah per satuan (mis. meter atau yard). Jumlah terjual "
       "diubah ke satuan ini sebelum dikalikan tarif.",
  impact="Jumlah penjualan dikonversi ke satuan ini sebelum dikalikan tarif komisi.",
  example="Satuan 'meter' · tarif Rp 500/meter → 100 yard ≈ 91,44 m → Rp 45.720",
  consumers=("routers/incentive_rates.py:create_rate",), risk="medium",
  ref="uom")

E("commission.default_margin_cap_pct", group="penjualan", section="komisi", type="pct", default=50.0,
  min=0, max=100, step=5, unit="% margin", scopes=("global", "entity"),
  simulate="commission_cap",
  label="Batas komisi terhadap margin",
  help="Komisi satu baris tidak boleh melebihi persen ini dari margin baris tersebut. Pengaman agar komisi tidak "
       "lebih besar dari keuntungan. Isi 0 = komisi tidak dibatasi margin.",
  impact="Komisi yang melewati batas dipotong otomatis dan diberi catatan pemotongan.",
  example="Margin baris Rp 1.000.000 · batas 50% · komisi hitung Rp 700.000 → dibayar Rp 500.000",
  consumers=("services/sales_force_service.py",), risk="medium")

E("commission.discount_threshold_type", group="penjualan", section="komisi", type="enum", default="pct",
  options=({"value": "pct", "label": "Persen diskon"},
           {"value": "rp_per_unit", "label": "Rupiah per satuan"}),
  scopes=("global", "entity"),
  label="Batas diskon dihitung dalam",
  help="Menentukan apakah batas diskon di bawah dibaca sebagai persen atau rupiah per satuan.",
  impact="Mengubah cara ambang diskon dibandingkan sebelum mekanik pemotongan komisi aktif.",
  example="Persen · ambang 10 → diskon 12% memotong komisi",
  consumers=("services/sales_force_service.py",), risk="low")

E("commission.discount_threshold", group="penjualan", section="komisi", type="decimal", default=10.0,
  min=0, max=1000000, step=1, scopes=("global", "entity"), simulate="commission_discount",
  label="Batas diskon yang memotong komisi",
  help="Bila diskon satu baris melewati angka ini (persen atau rupiah per satuan, sesuai pilihan di atas), komisi "
       "sales untuk baris itu dipotong. Isi 0 = diskon berapa pun memotong komisi.",
  impact="Menentukan baris mana yang komisinya dipotong karena diskon terlalu besar.",
  example="Ambang 10% · diskon 15% → mekanik pemotongan aktif",
  consumers=("services/sales_force_service.py",),
  related=("commission.discount_mechanic",), risk="medium")

E("commission.discount_mechanic", group="penjualan", section="komisi", type="enum", default="tier_factor",
  options=({"value": "tier_factor", "label": "Kalikan faktor (mis. 50% komisi)"},
           {"value": "potong_rp", "label": "Kurangi rupiah per satuan"},
           {"value": "cutoff", "label": "Komisi hangus"}),
  scopes=("global", "entity"), simulate="commission_discount",
  label="Cara memotong komisi saat diskon besar",
  help="Pilih apa yang terjadi pada komisi bila diskon melewati ambang: dikalikan faktor, dikurangi rupiah per "
       "satuan, atau hangus.",
  impact="Menentukan besar komisi yang dibayarkan pada baris berdiskon besar.",
  example="Kalikan faktor 0,5 → komisi Rp 1.000.000 menjadi Rp 500.000",
  consumers=("services/sales_force_service.py",), risk="medium")

E("commission.discount_factor", group="penjualan", section="komisi", type="decimal", default=0.5,
  min=0, max=1, step=0.05, scopes=("global", "entity"), simulate="commission_discount",
  label="Faktor komisi saat diskon besar",
  help="Pengali komisi bila mekanik 'Kalikan faktor' dipakai. 0,5 = komisi tinggal separuh. Isi 0 = komisi baris "
       "itu hangus.",
  impact="Langsung mengubah nominal komisi baris berdiskon besar.",
  example="Faktor 0,25 → komisi Rp 800.000 menjadi Rp 200.000",
  consumers=("services/sales_force_service.py",), risk="medium",
  unit="× komisi")

E("commission.discount_potong_rp", group="penjualan", section="komisi", type="money", default=0.0,
  min=0, max=100000000, step=100, unit=RP, scopes=("global", "entity"),
  simulate="commission_discount",
  label="Potongan rupiah per satuan",
  help="Dipakai bila mekanik 'Kurangi rupiah per satuan' dipilih. Isi 0 = komisi tidak dikurangi.",
  impact="Mengurangi tarif komisi per satuan pada baris berdiskon besar.",
  example="Tarif Rp 500/m dipotong Rp 200 → komisi jadi Rp 300/m",
  consumers=("services/sales_force_service.py",), risk="low")

# ═══════════════════════════════════════════════════════════════════════════
# PERSETUJUAN & AMBANG
# ═══════════════════════════════════════════════════════════════════════════
E("approval.extra_levels", group="persetujuan", section="umum", type="table", default={},
  scopes=("global", "entity"), simulate="approval",
  label="Jenjang persetujuan tambahan",
  help="Persetujuan tingkat kedua dan seterusnya (mis. Direksi) untuk dokumen bernilai besar. Hanya berjalan bila "
       "dokumen itu sudah wajib disetujui pada tingkat pertama di tab Aturan Persetujuan.",
  impact="Menambah antrean persetujuan berjenjang (mis. Direksi) untuk dokumen bernilai besar.",
  example="PO ≥ Rp 500.000.000 → setelah Manajer, wajib disetujui Direksi",
  consumers=("services/approval_policy_service.py:default_rows_for",), risk="high",
  # KP-T4 — isi kunci ini pindah ke tabel kebijakan persetujuan (`approval_policies`).
  status="not_used", not_used_reason=_KPT4_TIDAK_DIPAKAI,
  row_shape="grouped_list",
  columns=[{"name": "doc_type", "label": "Jenis dokumen", "type": "enum", "options": [{"value": "purchase_order", "label": "Pesanan Pembelian (PO)"}, {"value": "sales_order", "label": "Pesanan penjualan", "not_used": True}, {"value": "purchase_requisition", "label": "Permintaan pembelian", "not_used": True}]}, {"name": "min_amount", "label": "Mulai nilai (Rp)", "type": "money", "default": 0}, {"name": "role", "label": "Peran penyetuju", "type": "enum", "ref": "role"}, {"name": "label", "label": "Nama tingkat", "type": "text"}])

# PENGINGAT ANTREAN PERSETUJUAN (permintaan pemilik 2026-08-15).
# Angka KPI yang benar hanya bekerja kalau orangnya membuka layar. Ambang ini menjawab
# "sejak umur berapa sebuah dokumen layak diteriaki": dokumen yang baru masuk hari ini
# tidak perlu pengingat, yang sudah menua wajib. Dinaikkan ke admin/pemilik otomatis
# bila umurnya sudah 2× ambang ini (antrean bukan menumpuk lagi, tapi MANDEK).
E("approval.reminder_min_days", group="persetujuan", section="umum", type="int", default=2,
  min=0, max=60, step=1, unit="hari", scopes=("global", "entity"),
  label="Ingatkan dokumen yang menunggu sejak",
  help="Pengingat harian hanya menyebut dokumen yang sudah menunggu keputusan minimal sekian hari; bila sudah dua "
       "kali lipatnya, pengingat juga dikirim ke admin. Isi 0 agar diingatkan sejak hari pertama.",
  impact="Menentukan isi pengingat harian 'keputusan yang menunggu Anda' di notifikasi "
         "manajer. Tidak mengubah dokumen apa pun — hanya kapan orang diberi tahu.",
  example="Ambang 2 hari · PO-00010 menunggu 12 hari → masuk pengingat & dinaikkan ke "
          "admin (12 ≥ 2×2)",
  consumers=("services/approval_reminder.py",), risk="low")

# INV-GL-DRIFT (lanjutan 2026-06). Selisih GL Persediaan vs nilai fisik roll adalah
# kelas cacat "salah tetapi tenang": tidak ada galat, tidak ada layar merah, hanya
# neraca yang perlahan berbohong. Ambang ini menjawab "selisih berapa yang layak
# membangunkan orang": pembulatan rupiah tidak, senilai satu roll wajib.
E("inventory.drift_alert_rupiah", group="pajak-pembukuan", section="tutup-buku", type="money",
  default=1000, min=0, max=1000000000, step=1000, unit="Rp",
  scopes=("global", "entity"),
  label="Selisih stok vs pembukuan yang diingatkan",
  help="Bila nilai stok fisik dan nilai persediaan di pembukuan berselisih lebih dari angka ini, petugas akunting "
       "diberi tahu setiap hari sampai dibereskan. Isi 0 agar selisih sekecil apa pun diberitahukan.",
  impact="Hanya menentukan KAPAN orang diberi tahu. Tidak mencatat apa pun di pembukuan dan tidak mengubah stok — "
         "penyesuaian tetap keputusan manusia.",
  example="Batas Rp 1.000 · fisik Rp 5.100.000 vs pembukuan Rp 4.200.000 → selisih Rp 900.000 diberitahukan ke "
          "pemegang akses Akuntansi",
  consumers=("services/inventory_drift_watch.py",), risk="low")

# PK-29 (IV-09, K-06) — true-up persediaan (jurnal ke Ekuitas Saldo Awal) hanya untuk PT yang masih mengisi saldo awal;
# sesudah PT bertransaksi, selisih dikoreksi lewat dokumennya. Ditegakkan endpoint true-up (`assert_trueup_allowed`);
# skrip impor stok awal yang memanggil fungsi layanan langsung tidak terkena.
E("inventory.trueup_hanya_saldo_awal", group="pajak-pembukuan", section="tutup-buku", type="bool", default=True,
  scopes=("global", "entity"),
  label="True-up persediaan hanya untuk saldo awal",
  help="Bila ya, true-up persediaan (tombol saldo awal di Rekonsiliasi Persediaan) hanya bisa dipakai PT yang belum "
       "punya transaksi persediaan (penerimaan, pengiriman, retur). Sesudah itu selisih harus dikoreksi lewat dokumennya.",
  impact="Bila dimatikan, selisih berapa pun antara nilai roll dan buku besar bisa disamakan lewat jurnal ke Ekuitas "
         "Saldo Awal.",
  example="PT baru mengimpor stok awal Rp 2.000.000.000 → boleh true-up. PT yang sudah berjalan dengan selisih "
          "Rp 5.000 → ditolak sampai penyebabnya dikoreksi.",
  risk="high", requires_reason=True, permission=("accounting", "manage"),
  consumers=("services/gl_service.py:assert_trueup_allowed",))

# T-01 Opsi B (2026-09). Klaim saga yang mati di tengah meninggalkan `saga_lock` —
# dokumen terkunci, aksi ulang 409. Ambang ini menjawab "sesudah berapa menit kunci
# dianggap MENGGANTUNG dan admin harus diberi tahu", bukan sekadar sedang berjalan.
E("saga.stuck_lock_minutes", group="sistem", section="rfid-proses", type="int",
  default=10, min=1, max=1440, step=1, unit="menit",
  scopes=("global",),
  label="Proses macet: beri tahu admin setelah",
  help="Bila sebuah proses (mis. batal pesanan, ganti roll, batal tagihan) terhenti di tengah jalan lebih lama dari "
       "sekian menit, admin diberi tahu tiap hari sampai dibereskan di tab Kunci Proses. Sistem tidak pernah "
       "membukanya sendiri.",
  impact="Hanya menentukan KAPAN admin diberi tahu. Kunci tidak pernah dilepas otomatis.",
  example="Batas 10 menit · proses batal pesanan pada SO-00012 terhenti 25 menit → admin diberi tahu beserta alasan "
          "gagal bila tercatat",
  consumers=("services/saga_lock_watch.py",), risk="low")

E("purchasing.price_deviation_approval_percent", group="pembelian", section="memesan", type="pct",  default=10.0, min=0, max=100, step=1, unit="%", scopes=("global", "entity"),
  simulate="price_deviation",
  label="Kenaikan harga beli yang wajib disetujui",
  help="Bila harga di PO lebih tinggi dari harga acuan pemasok melebihi persen ini, PO harus disetujui dulu. Isi 0 "
       "dibaca sistem sebagai 10%.",
  impact="Menentukan PO mana yang tertahan menunggu persetujuan karena harga naik.",
  example="Harga acuan Rp 100.000 · PO Rp 115.000 (+15%) · ambang 10% → wajib persetujuan",
  consumers=("routers/purchase_orders.py", "services/pr_sourcing_service.py"), risk="high")

# AS-01 (catatan demo 2026-09) — persetujuan NILAI manajer setelah Admin Sales DITIADAKAN.
E("sales.require_so_validation", group="penjualan", section="alur-pesanan", type="bool",
  default=False, scopes=("global", "entity"),
  label="Pesanan wajib disetujui manajer",
  help="Bila aktif, setiap pesanan baru menunggu persetujuan manajer sebelum bisa dikonfirmasi. Bila mati, pesanan "
       "yang sudah diverifikasi Admin Sales langsung siap dikonfirmasi; persetujuan kredit dan harga khusus tetap "
       "berlaku.",
  impact="Alur menjadi: Sales membuat → Admin Sales verifikasi → Admin Sales konfirmasi. "
         "Menyalakan kembali membuat setiap pesanan baru menunggu pengesahan manajer.",
  example="SO Rp 75 jt tanpa kredit berlebih → langsung 'Siap dikonfirmasi' di Meja Admin Sales",
  consumers=("services/so_approvals.py:require_validation_default",
             "routers/sales_orders.py", "routers/sales_orders_extra.py"),
  related=("sales_admin.require_verification_before_confirm",), risk="high")

# FASE E-8 (E8.13) — VERIFIKASI ADMINISTRATIF sebelum Konfirmasi SO.
# Bawaan SENGAJA MATI: instalasi yang sudah berjalan tidak boleh mendadak menolak
# konfirmasi yang tadinya sah. Pemilik menyalakannya di sini bila ingin "tidak ada
# pesanan jalan ke gudang sebelum kelengkapannya diperiksa" jadi aturan mengikat.
E("sales_admin.require_verification_before_confirm", group="penjualan", section="alur-pesanan", type="bool",
  default=True, scopes=("global", "entity"),
  label="Pesanan wajib diverifikasi Admin Sales",
  help="Bila aktif, pesanan baru bisa dikonfirmasi setelah Admin Sales memeriksa alamat, penerima, syarat bayar, "
       "dan isi pesanan. Ini pemeriksaan kelengkapan, bukan persetujuan nilai.",
  impact="Konfirmasi pesanan yang belum diverifikasi ditolak beserta daftar kekurangannya. Pesanan yang sudah "
         "diverifikasi tidak terpengaruh.",
  example="Pesanan tanpa nama penerima & telepon → konfirmasi ditolak sampai alamat dilengkapi",
  consumers=("services/so_verify_service.py:assert_ready_to_confirm",
             "routers/sales_orders_extra.py:confirm_order"),
  related=("approval.extra_levels",), risk="medium")

# ═══════════════════════════════════════════════════════════════════════════
# PEMBELIAN & TAGIHAN SUPPLIER
# ═══════════════════════════════════════════════════════════════════════════
E("purchasing.receive_tolerance_percent", group="penerimaan", section="menerima", type="pct", default=2.0,
  min=0, max=100, step=0.5, unit="%", scopes=("global", "entity"), simulate="receiving_over",
  label="Kelebihan kedatangan yang masih diterima",
  help="Persen kelebihan barang datang di atas jumlah PO yang masih boleh diterima. Di atasnya penerimaan ditolak "
       "atau ditandai, sesuai “Tolak penerimaan melebihi sisa PO”. Isi 0 = tidak boleh menerima lebih dari sisa PO.",
  impact="Penerimaan di atas PO + toleransi ini akan ditolak atau diberi peringatan.",
  example="PO 1.000 yard · toleransi 2% → boleh terima s/d 1.020 yard",
  consumers=("services/receiving_uom_service.py:receive_tolerance_pct",),
  related=("receiving.block_over_remaining",), risk="medium")

E("purchasing.restock_source_unknown", group="pembelian", section="memesan", type="enum", default="warn",
  options=({"value": "warn", "label": "Peringatkan — PR/PO/MKO tetap boleh, tercatat 'belum diatur'"},
           {"value": "block", "label": "Tolak — MD wajib mengisi sumber restock artikel dulu"}),
  scopes=("global", "entity"),
  label="Barang tanpa sumber beli: tolak/ingatkan",
  help="Bila MD belum menentukan barang ini dibeli dari pemasok atau dibuat lewat makloon, pilih apakah permintaan "
       "pembelian, PO, dan order makloon-nya ditolak atau hanya diberi peringatan.",
  impact="Berlaku saat membuat permintaan pembelian, PO manual, dan order makloon barang jadi.",
  example="Tolak → permintaan pembelian produk KNT-0067 ditolak sampai MD memilih pemasok/makloon",
  consumers=("services/restock_source_service.py:unknown_policy",), risk="medium")
E("purchasing.require_supplier_master", group="pembelian", section="memesan", type="bool", default=False,
  scopes=("global", "entity"), simulate="po_supplier",
  label="PO wajib pilih pemasok terdaftar",
  help="Bila aktif, PO tidak boleh diisi nama pemasok bebas; harus memilih dari daftar pemasok.",
  impact="Pembuatan PO tanpa pemasok terdaftar ditolak, supaya data pemasok rapi dan tagihannya bisa dicocokkan.",
  example="Aktif → PO tanpa pemasok terdaftar ditolak",
  consumers=("routers/purchase_orders.py:_create_po_core",), risk="medium")

E("purchasing.qc_on_receipt", group="penerimaan", section="menerima", type="bool", default=True,
  scopes=("global", "entity"),
  label="Barang masuk lewat karantina QC",
  help="Bila aktif, barang yang diterima masuk status karantina dulu dan harus lulus inspeksi "
       "sebelum bisa dijual. Berlaku untuk penerimaan PO dan hasil langkah TERAKHIR Order Makloon "
       "(langkah tengah tidak dikarantina agar rantai proses tidak tertahan).",
  impact="Menambah langkah inspeksi QC pada alur penerimaan; stok belum tersedia sebelum lulus.",
  example="Aktif → 20 roll diterima masuk 'karantina', menunggu Inspeksi QC",
  consumers=("services/inbound_qc_common.py:qc_on_receipt_enabled", "services/inbound_complete_service.py",
             "services/makloon_receipt_qc.py:receipt_policy", "services/qc_service.py"), risk="medium")

E("purchasing.allow_item_discount", sensitif_baca=False,  # KF-T1 — dibaca layar semua pengguna
  group="pembelian", section="memesan", type="bool", default=True,
  scopes=("global", "entity"), simulate="pricing",
  label="Izinkan diskon per baris (pembelian)",
  help="Mengizinkan potongan harga per baris pada Pesanan Pembelian.",
  impact="Menentukan apakah diskon baris PO dihitung saat menyusun DPP dan PPN masukan.",
  example="Aktif · baris Rp 5.000.000 diskon 3% → dibayar Rp 4.850.000",
  consumers=("services/config_service.py:compute_order_pricing",), risk="low")

E("purchasing.allow_order_discount", sensitif_baca=False,  # KF-T1 — dibaca layar semua pengguna
  group="pembelian", section="memesan", type="bool", default=True,
  scopes=("global", "entity"), simulate="pricing",
  label="Izinkan diskon total (pembelian)",
  help="Mengizinkan satu potongan untuk seluruh Pesanan Pembelian.",
  impact="Menentukan apakah diskon order PO dipakai dalam perhitungan total & pajak masukan.",
  example="Aktif · diskon 1% dari Rp 50.000.000 → potongan Rp 500.000",
  consumers=("services/config_service.py:compute_order_pricing",), risk="low")

E("purchasing.bill_qty_tolerance_percent", sensitif_baca=False,  # KF-T1 — dibaca layar semua pengguna
  group="pembelian", section="tagihan", type="pct", default=0.0,
  min=0, max=100, step=0.5, unit="%", scopes=("global", "entity"), simulate="bill_match",
  label="Toleransi jumlah di tagihan pemasok",
  help="Selisih jumlah di tagihan pemasok dibanding barang yang benar-benar diterima yang masih boleh lewat tanpa "
       "keputusan. Isi 0 = jumlah harus sama persis.",
  impact="Tagihan dengan selisih jumlah di atas toleransi akan ditolak/ditandai perlu keputusan.",
  example="Diterima 1.000 yard · ditagih 1.010 · toleransi 0% → tagihan ditolak",
  consumers=("services/three_way_policy.py",), risk="medium")

E("purchasing.bill_price_tolerance_percent", sensitif_baca=False,  # KF-T1 — dibaca layar semua pengguna
  group="pembelian", section="tagihan", type="pct", default=5.0,
  min=0, max=100, step=0.5, unit="%", scopes=("global", "entity"), simulate="bill_match",
  label="Toleransi harga tagihan pemasok",
  help="Selisih harga satuan pada tagihan pemasok dibanding harga PO yang masih boleh lewat. Isi 0 = harga harus "
       "sama persis.",
  impact="Tagihan dengan harga di atas toleransi ditandai selisih dan butuh keputusan.",
  example="Harga PO Rp 100.000 · ditagih Rp 108.000 (+8%) · toleransi 5% → ditandai selisih",
  consumers=("services/three_way_policy.py",), risk="medium")

# PK-26 (IV-01, K-05) — porsi voucher biaya masuk untuk roll yang sudah keluar (terkirim, retur ke pemasok, antar-PT)
# tidak lagi mengendap di persediaan: dibebankan ke HPP (bawaan K-05) atau ke akun biaya masuk pembelian
# (`pembelian.landed_cost`, Pemetaan Akun yang sudah ada — tanpa akun/kunci pemetaan baru).
E("inventory.landed_cost_porsi_terjual", group="pembelian", section="tagihan", type="enum", default="hpp",
  options=({"value": "hpp", "label": "Bebankan ke HPP periode berjalan"},
           {"value": "varians", "label": "Catat di akun biaya masuk pembelian"}),
  scopes=("global", "entity"),
  label="Biaya masuk untuk barang yang sudah terjual",
  help="Menentukan ke mana biaya angkut/bea dibukukan untuk roll yang sudah terkirim ke pelanggan saat voucher biaya "
       "masuk disetujui. Roll yang masih di gudang selalu menambah nilai persediaan.",
  impact="Mengubah akun beban pada jurnal voucher biaya masuk berikutnya. Voucher yang sudah disetujui tidak berubah.",
  example="Voucher Rp 3.000.000 untuk dua roll senilai sama, satu sudah terjual: Rp 1.500.000 ke persediaan, "
          "Rp 1.500.000 ke HPP (atau ke akun biaya masuk pembelian).",
  risk="high", requires_reason=True, permission=("accounting", "manage"),
  consumers=("services/landed_cost_service.py:expensed_to_for",))   # dibaca `approve_landed_cost` (PERIKSA)

# ═══════════════════════════════════════════════════════════════════════════
# STOK, SATUAN & ALOKASI
# ═══════════════════════════════════════════════════════════════════════════
E("inventory.default_uom", group="stok", section="kerja-gudang", type="text", default="meter",
  scopes=("global", "entity"),
  label="Satuan bawaan produk baru",
  help="Satuan yang otomatis terpilih ketika membuat produk baru.",
  impact="Mempengaruhi satuan awal produk baru dan tampilan stok bawaan.",
  example="'meter' → produk baru langsung bersatuan meter",
  consumers=("routers/products.py:create_product",), risk="low",
  ref="uom")

E("inventory.min_cut_qty", sensitif_baca=False,  # KF-T1 — dibaca layar semua pengguna
  group="stok", section="memilih-stok", type="decimal", default=0.5,
  min=0, max=1000, step=0.1, unit="satuan dasar", scopes=("global", "entity"),
  simulate="min_cut",
  label="Minimum panjang potong kain",
  help="Panjang terkecil yang boleh dipotong dari satu roll. Mencegah sisa potongan yang terlalu pendek sehingga "
       "tidak terjual. Isi 0 = tanpa batas terkecil.",
  impact="Pesanan/pengambilan dengan jumlah di bawah angka ini ditolak dengan pesan jelas.",
  example="Minimum 0,5 m → permintaan potong 0,3 m ditolak",
  consumers=("routers/sales_orders.py:_validate_min_cut",), risk="medium")

E("inventory.intercompany_transfer_required", group="stok", section="memilih-stok", type="bool", default=True,
  scopes=("global", "entity"), simulate="interco",
  label="Jual stok PT lain wajib lewat transfer",
  help="Bila aktif, satu PT tidak boleh langsung menjual stok milik PT lain; harus dibuat transaksi antar-PT lebih "
       "dulu. Selama aktif, “Boleh memakai stok PT lain” tidak berlaku.",
  impact="Pesanan yang memakai stok milik PT lain ditolak sampai transfer dibuat. Menjaga kebenaran laporan laba "
         "per PT.",
  example="Aktif → pesanan di KSC yang mengambil roll milik KANDA ditolak sampai transfer dibuat",
  consumers=("services/config_service.py:get_allocation_policy",), risk="high")

# K-05 (keputusan pemilik 26 Okt 2026) — kelas laju jual Analitik Stok HANYA dari moving average penjualan
# (persentil per satuan). Ambang lama "hari sejak jual terakhir" tidak lagi dibaca mesin.
E("inventory.stock_analytics.fast_max_days", group="stok", section="laris-lambat", type="duration",
  default=30, min=1, max=365, step=1, unit="hari", scopes=("global", "entity"),
  status="not_used",
  not_used_reason="Diganti K-05 (26 Okt 2026): kelas Analitik Stok kini dari moving average penjualan & "
                  "persentil per satuan — lihat 'Best seller — persen teratas' dan setelan terkait.",
  label="Batas hari barang 'Cepat Laku' (lama)",
  help="Aturan lama: barang yang terjual dalam rentang hari ini dihitung Cepat Laku.",
  impact="Tidak berpengaruh lagi.",
  example="—", risk="low")

E("inventory.stock_analytics.slow_max_days", group="stok", section="laris-lambat", type="duration",
  default=90, min=1, max=1095, step=1, unit="hari", scopes=("global", "entity"),
  status="not_used",
  not_used_reason="Diganti K-05 (26 Okt 2026): kelas Analitik Stok kini dari moving average penjualan & "
                  "persentil per satuan — lihat 'Slow moving — persen terbawah' dan setelan terkait.",
  label="Batas hari barang 'Lambat' (lama)",
  help="Aturan lama: di atas batas Cepat Laku sampai batas ini = Lambat; lebih dari itu = Stok Mati.",
  impact="Tidak berpengaruh lagi.",
  example="—", risk="low")

E("inventory.stock_analytics.velocity_window_days", group="stok", section="laris-lambat", type="duration",
  default=90, min=7, max=730, step=1, unit="hari", scopes=("global", "entity"),
  simulate="stock_class",
  label="Analitik stok: hitung penjualan berapa hari",
  help="Jumlah hari ke belakang untuk menghitung rata-rata penjualan per hari tiap barang. Lebih pendek lebih peka "
       "tren; lebih panjang lebih stabil.",
  impact="Menjadi dasar kelas Best seller / Normal / Slow moving / Tidak bergerak di Analitik Stok dan angka "
         "'cukup untuk' (hari persediaan). Jendela pendek lebih peka tren, jendela panjang lebih stabil.",
  example="90 hari · terjual 900 yard → moving average 10 yard/hari",
  consumers=("services/stock_analytics_service.py:compute_stock_analytics",),
  related=("inventory.stock_analytics.best_seller_pct", "inventory.stock_analytics.slow_moving_pct",
           "inventory.stock_analytics.new_sku_age_days"), risk="low")

E("inventory.stock_analytics.best_seller_pct", group="stok", section="laris-lambat", type="pct",
  default=20, min=1, max=50, step=1, unit="%", scopes=("global", "entity"),
  simulate="stock_class",
  label="Analitik stok: persen barang terlaris",
  help="Barang diurutkan menurut rata-rata penjualannya (per satuan yang sama); sekian persen teratas disebut "
       "Terlaris.",
  impact="Menambah/mengurangi jumlah SKU berlabel Best seller di Analitik Stok.",
  example="20% · 50 SKU bersatuan yard terjual → 10 SKU yard dengan laju jual tertinggi = Best seller",
  consumers=("services/stock_analytics_service.py:compute_stock_analytics",),
  related=("inventory.stock_analytics.slow_moving_pct",), risk="low")

E("inventory.stock_analytics.slow_moving_pct", group="stok", section="laris-lambat", type="pct",
  default=20, min=1, max=50, step=1, unit="%", scopes=("global", "entity"),
  simulate="stock_class",
  label="Analitik stok: persen barang lambat laku",
  help="Sekian persen terbawah di antara barang yang terjual disebut Lambat laku. Barang berstok yang tidak terjual "
       "sama sekali disebut Tidak bergerak.",
  impact="Menambah/mengurangi daftar SKU Slow moving yang perlu didorong penjualannya.",
  example="20% · 50 SKU bersatuan yard terjual → 10 SKU yard dengan laju jual terendah = Slow moving",
  consumers=("services/stock_analytics_service.py:compute_stock_analytics",),
  related=("inventory.stock_analytics.best_seller_pct",), risk="low")

E("inventory.stock_analytics.new_sku_age_days", group="stok", section="laris-lambat", type="duration",
  default=90, min=0, max=730, step=1, unit="hari", scopes=("global", "entity"),
  simulate="stock_class",
  label="Analitik stok: barang dianggap baru selama",
  help="Barang yang umurnya kurang dari sekian hari diberi label Baru dan belum diperingkat. Isi 0 bila tidak perlu "
       "kelas Baru.",
  impact="Mengubah SKU mana yang dikecualikan dari peringkat Best seller / Slow moving / Tidak bergerak.",
  example="90 hari · produk masuk 40 hari lalu → Baru (belum diperingkat)",
  consumers=("services/stock_analytics_service.py:compute_stock_analytics",),
  related=("inventory.stock_analytics.velocity_window_days",), risk="low")

E("inventory.reorder.velocity_window_days", group="stok", section="laris-lambat", type="duration",
  default=90, min=7, max=730, step=1, unit="hari", scopes=("global", "entity"),
  label="Pesan ulang: hitung penjualan berapa hari",
  help="Jumlah hari penjualan yang dipakai untuk menghitung usulan pembelian ulang.",
  impact="Mengubah angka usulan jumlah pada Saran Reorder & Purchase Requisition otomatis.",
  example="60 hari → usulan lebih responsif terhadap tren terbaru",
  consumers=("services/purchase_requisition_service.py",), risk="low")

E("inventory.reorder.safety_days", group="stok", section="laris-lambat", type="duration", default=7,
  min=0, max=180, step=1, unit="hari", scopes=("global", "entity"), simulate="reorder",
  label="Pesan ulang: cadangan hari aman",
  help="Tambahan hari persediaan di atas lama kirim pemasok agar stok tidak sampai habis. Lebih besar lebih aman, "
       "tetapi modal tertahan lebih banyak. Isi 0 = hanya lama kirim pemasok yang dihitung, tanpa cadangan.",
  impact="Menaikkan titik pesan ulang → stok lebih aman tapi modal tertahan lebih besar.",
  example="Jual 10 yard/hari · lead time 14 hari · safety 7 → titik pesan 210 yard",
  consumers=("services/purchase_requisition_service.py",), risk="medium")

E("allocation.mode", group="stok", section="memilih-stok", type="enum", default="auto",
  options=({"value": "auto", "label": "Otomatis penuh"},
           {"value": "assisted", "label": "Diusulkan sistem, dikonfirmasi petugas"},
           {"value": "manual", "label": "Manual sepenuhnya"}),
  scopes=("global", "entity"),
  label="Cara memilih stok untuk pesanan",
  help="Menentukan seberapa besar campur tangan petugas saat sistem memilih roll untuk pesanan.",
  impact="Mengubah alur kerja gudang: otomatis langsung terpilih, manual harus dipilih sendiri.",
  example="Diusulkan sistem → sistem mengusulkan 3 roll, petugas menyetujui atau menukar",
  consumers=("services/config_service.py:get_allocation_policy", "services/roll_service.py"),
  risk="medium")

E("allocation.roll_pick_sales", sensitif_baca=False,  # KF-T1 — dibaca layar semua pengguna
  group="stok", section="memilih-stok", type="bool", default=True,
  scopes=("global", "entity"),
  label="Sales boleh memilih roll saat memesan",
  help="Bila mati, sales hanya mengisi jumlah; roll dipilihkan sistem (yang masuk lebih dulu) dan Admin Sales bisa "
       "menggantinya di detail pesanan.",
  impact="Menggeser keputusan pemilihan roll dari sales lapangan ke Admin Sales (alokasi manual).",
  example="OFF → sales pesan 200 yard; sistem reserve FIFO di lokasi pesanan; Admin Sales tukar ke roll lot A-113",
  consumers=("routers/sales_orders.py", "routers/sales_orders_extra.py:reallocate_line_rolls"),
  risk="medium")

E("allocation.makloon_reserve_mode", group="stok", section="memilih-stok", type="enum", default="block",
  options=({"value": "block", "label": "Blokir — stok cadangan makloon tidak bisa dijual"},
           {"value": "approve", "label": "Boleh dipakai dengan persetujuan manajer"}),
  scopes=("global", "entity"),
  label="Stok cadangan makloon boleh dijual?",
  help="Bahan yang sudah dicadangkan untuk makloon dikurangkan dari stok yang bisa dijual. Pilih apakah pesanan "
       "yang melebihi stok bebas ditolak, atau boleh memakai cadangan itu dengan persetujuan manajer.",
  impact="Mencegah stok yang sama dijanjikan ke pelanggan dan ke makloon sekaligus.",
  example="Stok 500 yd, cadangan makloon 300 yd → sales hanya bisa memesan 200 yd (mode Blokir)",
  consumers=("services/roll_service.py:makloon_guard", "services/sales_order_helpers.py:reserve_roll_mode_item"),
  risk="medium")

E("allocation.priority_order", group="stok", section="memilih-stok", type="list",
  default=["owner", "lot", "location", "roll_efficiency"], scopes=("global", "entity"),
  label="Urutan pertimbangan memilih roll",
  help="Urutan yang dipakai sistem saat memilih roll: pemilik (selalu pertama), kesamaan lot, kedekatan gudang, dan "
       "efisiensi sisa.",
  impact="Mengubah roll mana yang dipilih lebih dulu: kesamaan lot, kedekatan gudang, atau efisiensi sisa.",
  example="PT pemilik stok, Lokasi gudang, Lot yang sama → utamakan gudang terdekat sebelum kesamaan lot",
  consumers=("services/config_service.py:_sanitize_alloc", "services/roll_service.py"),
  risk="medium",
  items="options",
  ordered=True,
  options=[{"value": "owner", "label": "PT pemilik stok"}, {"value": "lot", "label": "Lot yang sama"}, {"value": "location", "label": "Lokasi gudang"}, {"value": "roll_efficiency", "label": "Roll paling hemat"}])

E("allocation.lot_mode", group="stok", section="memilih-stok", type="enum", default="prefer_single",
  options=({"value": "prefer_single", "label": "Usahakan satu lot"},
           {"value": "strict_single", "label": "Wajib satu lot"},
           {"value": "allow_mixed", "label": "Boleh campur lot"}),
  # KF-T5 — lapisan pelanggan dicabut: mesin memakai isian `lot_policy` kartu pelanggan, bukan lapisan pengaturan.
  scopes=("global", "entity"),
  label="Kebijakan campur lot",
  help="Seberapa ketat satu pesanan harus berasal dari satu lot produksi (penting untuk kesamaan warna). Untuk "
       "pelanggan tertentu, atur di kartu pelanggan (Kebijakan lot).",
  impact="Mode 'wajib satu lot' bisa membuat pesanan tidak bisa dipenuhi walau total stok cukup.",
  example="Wajib satu lot → pesanan 600 yard ditolak bila lot terbesar hanya 400 yard",
  consumers=("services/config_service.py:get_allocation_policy", "services/roll_service.py"),
  risk="high")

E("allocation.lot_selection", group="stok", section="memilih-stok", type="enum", default="fifo",
  # UAT 24 Okt (P9.6, keputusan pemilik) — kain tidak berkedaluwarsa: FIFO (tanggal masuk) setelah LOKASI pesanan.
  # Nilai lama "fefo" tetap sah (diperlakukan sama dengan FIFO) supaya pengaturan tersimpan tidak rusak.
  options=({"value": "fifo", "label": "Yang masuk lebih dulu"},
           {"value": "fefo", "label": "Yang masuk lebih dulu (sama dengan pilihan pertama)"},
           {"value": "smallest_fit", "label": "Sisa terkecil yang cukup"},
           {"value": "largest_fit", "label": "Sisa terbesar"}),
  scopes=("global", "entity"),
  label="Urutan pengambilan lot",
  help="Aturan memilih lot mana yang dipakai lebih dulu.",
  impact="Mengubah umur stok yang keluar dan potensi barang mengendap.",
  example="Sisa terkecil yang cukup → habiskan roll sisa 40 yard sebelum membuka roll penuh",
  consumers=("services/config_service.py:get_allocation_policy", "services/roll_service.py"),
  risk="medium")

E("allocation.location_pref", group="stok", section="memilih-stok", type="enum", default="single_warehouse",
  options=({"value": "single_warehouse", "label": "Satu gudang saja"},
           {"value": "nearest_customer", "label": "Gudang terdekat pelanggan"},
           {"value": "fewest_splits", "label": "Paling sedikit pecah kiriman"}),
  scopes=("global", "entity"),
  label="Preferensi gudang pengambilan",
  help="Menentukan gudang mana yang diutamakan saat stok tersebar di beberapa gudang.",
  impact="Mempengaruhi biaya kirim dan jumlah surat jalan per pesanan.",
  example="Gudang terdekat pelanggan → ambil dari gudang Solo untuk pelanggan Yogyakarta",
  consumers=("services/config_service.py:get_allocation_policy", "services/roll_service.py"),
  risk="low")

E("allocation.allow_intercompany", group="stok", section="memilih-stok", type="bool", default=True,
  scopes=("global", "entity"),
  label="Boleh memakai stok PT lain",
  help="Mengizinkan pesanan dipenuhi dari stok milik PT lain dalam grup. Tidak berlaku selama “Jual stok PT lain "
       "wajib lewat transfer” masih aktif.",
  impact="Bila mati, pesanan hanya dilayani stok milik PT penerbit pesanan.",
  example="Mati → SO KSC hanya boleh memakai roll milik KSC",
  consumers=("services/config_service.py:_sanitize_alloc", "services/roll_service.py"),
  related=("inventory.intercompany_transfer_required",), risk="high")

E("allocation.allow_partial", group="stok", section="memilih-stok", type="bool", default=True,
  scopes=("global", "entity"),
  label="Boleh alokasi sebagian",
  help="Mengizinkan sistem mengalokasikan sebagian jumlah bila stok belum cukup.",
  impact="Bila mati, pesanan yang stoknya kurang tidak dialokasikan sama sekali.",
  example="Aktif → pesanan 1.000 yard dialokasi 700, sisa 300 jadi backorder",
  consumers=("services/config_service.py:_sanitize_alloc", "services/roll_service.py"),
  risk="medium")

E("allocation.dye_lot_strict", group="stok", section="memilih-stok", type="bool", default=False,
  # KF-T5 — lapisan pelanggan dicabut: mesin memakai isian `enforce_single_dye_lot` kartu pelanggan.
  scopes=("global", "entity"),
  label="Wajib satu dye lot (warna sama)",
  help="Memaksa seluruh kiriman berasal dari satu nomor celup agar warna persis sama."
       " Untuk pelanggan tertentu, atur di kartu pelanggan (Kebijakan lot).",
  impact="Menaikkan kualitas warna tetapi memperbesar kemungkinan pesanan tidak bisa dipenuhi.",
  example="Aktif → 2 roll dye lot berbeda tidak boleh digabung dalam 1 pesanan",
  consumers=("services/config_service.py:_sanitize_alloc", "services/roll_service.py"),
  risk="high")

# ═══════════════════════════════════════════════════════════════════════════
# KUALITAS (QC)
# ═══════════════════════════════════════════════════════════════════════════
E("qc.four_point_enabled", group="kualitas", section="inspeksi", type="bool", default=True,
  scopes=("global", "entity"), simulate="qc_grade",
  label="Aktifkan inspeksi 4-Point",
  help="Metode standar tekstil: tiap cacat diberi poin menurut panjangnya, lalu total poin menjadi acuan grade roll.",
  impact="Bila mati, layar Inspeksi QC tidak meminta rincian 4-point dan grade ditetapkan manual.",
  example="Mati → petugas langsung memilih grade tanpa menghitung poin cacat",
  consumers=("routers/qc_inspection.py:inspect",), risk="medium")

E("qc.grade_thresholds.a_max", group="kualitas", section="inspeksi", type="decimal", default=20.0,
  min=0, max=1000, step=1, unit="poin", scopes=("global", "entity"),
  simulate="qc_grade",
  label="Poin maksimum Grade A",
  help="Total poin cacat paling tinggi yang masih Grade A. Dipakai sebagai saran grade; bila batas poin sudah diisi "
       "di Master Grade Mutu, angka di sana yang dipakai. Isi 0 dibaca sistem sebagai 20.",
  impact="Mengubah grade hasil inspeksi → mempengaruhi harga jual dan klaim ke pemasok.",
  example="Batas 20 · hasil 18 poin → Grade A",
  consumers=("services/qc_inspection_service.py", "services/grade_service.py"),
  related=("qc.grade_thresholds.b_max",), risk="high")

E("qc.grade_thresholds.b_max", group="kualitas", section="inspeksi", type="decimal", default=40.0,
  min=0, max=1000, step=1, unit="poin", scopes=("global", "entity"),
  simulate="qc_grade",
  label="Poin maksimum Grade B",
  help="Batas atas poin untuk Grade B. Rentang di antara batas Grade A dan angka ini dibagi rata menjadi A1, A2, "
       "dan B; di atas angka ini roll masuk grade terendah. Isi 0 dibaca sistem sebagai 40.",
  impact="Menentukan kain mana yang turun ke Grade C dan wajib diskon/klaim.",
  example="Batas 40 · hasil 45 poin → grade terendah (BS)",
  consumers=("services/qc_inspection_service.py", "services/grade_service.py"), risk="high")

# Trial 22 Okt 2026 (F5, keputusan pemilik) — grade roll ditentukan PETUGAS QC dari total poin; untuk sekarang sistem
# tidak mengisi grade otomatis. Nyalakan bila kelak grade mau dihitung sistem memakai ambang di atas.
E("qc.grade_from_points", group="kualitas", section="inspeksi", type="bool", default=False,
  scopes=("global", "entity"),
  label="Grade roll diisi otomatis dari total poin",
  help="Mati (bawaan): petugas QC mengisi sendiri kode cacat, poin, dan grade roll; total poin hanya acuan. Hidup: "
       "grade yang dikosongkan petugas diisi sistem dari total poin.",
  impact="Bila mati, hasil 4-point yang disimpan tanpa grade ditolak dengan pesan 'isi grade roll'. "
         "Bila hidup, grade kosong = saran sistem dari total poin.",
  example="Mati → roll 18 poin, petugas memilih sendiri Grade A di Lembar Inspect",
  consumers=("services/qc_inspection_service.py:grade_auto",), risk="high")

E("qc.color_mismatch_action", group="kualitas", section="tidak-sesuai", type="enum", default="tahan",
  scopes=("global", "entity"),
  options=[{"value": "abaikan", "label": "Abaikan (hanya dicatat)"},
           {"value": "peringatkan", "label": "Beri peringatan, barang tetap masuk"},
           {"value": "tahan", "label": "TAHAN barang sampai manajer memutuskan"}],
  label="Bila warna beda dari sample disetujui",
  help="Menentukan apa yang terjadi bila petugas menandai warna kain berbeda dari sample yang sudah disetujui: "
       "dicatat saja, diberi peringatan, atau roll ditahan sampai manajer memutuskan.",
  impact="Pada pilihan TAHAN, roll tidak bisa ditempatkan ke bin (putaway) sebelum "
         "manajer melepasnya ber-alasan — barang tidak bisa terjual diam-diam.",
  example="Tahan → petugas gudang melihat pesan “roll ditahan: warna beda dari "
          "KSC/SMP-00001 — mintakan keputusan manajer”",
  consumers=("services/inspection_service.py:_policy",
             "services/qc_inspection_service.py:inspect_roll",
             "services/location_service.py:putaway_roll"),
  related=("qc.handfeel_mismatch_action",), risk="high")

E("qc.handfeel_mismatch_action", group="kualitas", section="tidak-sesuai", type="enum", default="peringatkan",
  scopes=("global", "entity"),
  options=[{"value": "abaikan", "label": "Abaikan (hanya dicatat)"},
           {"value": "peringatkan", "label": "Beri peringatan, barang tetap masuk"},
           {"value": "tahan", "label": "TAHAN barang sampai manajer memutuskan"}],
  label="Bila handfeel beda dari sample disetujui",
  help="Menentukan apa yang terjadi bila rasa dan konstruksi kain (gramasi, lebar, susut, handfeel) menyimpang dari "
       "sample: dicatat saja, diberi peringatan, atau roll ditahan.",
  impact="Pada pilihan TAHAN, perlakuannya sama seperti selisih warna: roll tidak boleh "
         "putaway sebelum manajer memutuskan.",
  example="Peringatkan → hasil inspeksi menampilkan catatan selisih, barang tetap masuk gudang",
  consumers=("services/inspection_service.py:_policy",
             "services/qc_inspection_service.py:inspect_roll"),
  related=("qc.color_mismatch_action",), risk="medium")

# B1 (keputusan pemilik 26 Okt 2026) — SPK QC ditutup "Diterima seluruhnya" padahal masih ada roll ditahan/gagal QC.
E("qc.accept_all_with_hold_action", group="kualitas", section="tidak-sesuai", type="enum", default="peringatkan",
  scopes=("global", "entity"),
  options=[{"value": "peringatkan", "label": "Beri peringatan, SPK tetap bisa ditutup (roll tetap ditahan)"},
           {"value": "blokir", "label": "Blokir — wajib 'Diterima sebagian'/'Ditolak' atau putus tahanan dulu"}],
  label="Tutup SPK saat masih ada roll ditahan",
  help="Bila keputusan SPK “Diterima seluruhnya” tetapi masih ada roll yang ditahan: beri peringatan lalu boleh "
       "ditutup (roll tetap ditahan), atau tolak sampai tahanannya diputus.",
  impact="Pada pilihan Blokir, server menolak keputusan 'Diterima seluruhnya' selama masih ada roll ditahan — "
         "petugas harus memilih 'Diterima sebagian'/'Ditolak' atau melepas/menolak tahanannya lebih dulu.",
  example="Peringatkan → SPK 10 roll, 1 roll gagal 4-point: dialog “1 roll masih ditahan (RL-00005)”, "
          "SPK tetap bisa ditutup dan RL-00005 tetap ditahan",
  consumers=("services/inspection_service.py:finish", "services/inspection_service.py:meta"), risk="medium")

# UAT 24 Okt 2026 (P11.2/P11.3, permintaan pemilik) — MD Quality & QC 4-point boleh memeriksa SEBAGIAN roll (sampling).
E("qc.md_sampling_pct", group="kualitas", section="jumlah-cek", type="int", default=0,
  min=0, max=100, step=5, unit="%", scopes=("global", "entity"),
  label="Cek MD Quality: persen roll minimal",
  help="SPK MD Quality boleh ditutup setelah sekian persen roll dicek. Isi 0 bila cukup satu roll. Roll yang tidak "
       "dicek tetap lepas karantina tetapi diberi tanda.",
  impact="Roll yang tidak dicek tetap lepas karantina, tetapi ditandai 'MDQ sampling' (bukan 'MDQ ✓') — "
         "terlihat di daftar roll dan bisa disaring di stok.",
  example="20% · kedatangan 10 roll → minimal 2 roll dicek; 8 roll lain bertanda MDQ sampling",
  consumers=("services/inspection_service.py:sampling_rule",), related=("qc.md_sampling_min",), risk="medium")

E("qc.md_sampling_min", group="kualitas", section="jumlah-cek", type="int", default=1,
  min=1, max=1000, step=1, unit="roll", scopes=("global", "entity"),
  label="Cek MD Quality: jumlah roll minimal",
  help="Jumlah roll paling sedikit yang harus dicek MD Quality per SPK, dipakai bersama persen di atas.",
  impact="SPK MD tidak bisa ditutup sebelum jumlah ini tercapai (atau semua roll bila kedatangannya lebih sedikit).",
  example="min 1 → kedatangan 3 roll dengan sampling 0% cukup 1 roll dicek",
  consumers=("services/inspection_service.py:sampling_rule",), related=("qc.md_sampling_pct",), risk="low")

E("qc.sampling_pct", group="kualitas", section="jumlah-cek", type="int", default=100,
  min=0, max=100, step=5, unit="%", scopes=("global", "entity"),
  label="Cek QC 4-point: persen roll wajib dicek",
  help="100 berarti semua roll di SPK wajib dicek. Di bawah 100, SPK boleh ditutup setelah sekian persen dicek; "
       "roll yang tidak dicek dikeluarkan dari SPK dan tetap bertanda “belum 4-point”. Isi 0 = cukup sejumlah roll "
       "minimal yang wajib dicek.",
  impact="Menentukan kapan SPK QC 4-point boleh ditutup. Pilih roll yang mau diperiksa saat membuat SPK.",
  example="30% · SPK 10 roll → cukup 3 roll dicek; 7 roll lain keluar dari SPK dan tetap 'belum 4-point'",
  consumers=("services/inspection_service.py:sampling_rule",), related=("qc.sampling_min",), risk="medium")

E("qc.sampling_min", group="kualitas", section="jumlah-cek", type="int", default=1,
  min=1, max=1000, step=1, unit="roll", scopes=("global", "entity"),
  label="Cek QC 4-point: jumlah roll minimal",
  help="Jumlah roll paling sedikit yang harus dicek per SPK QC 4-point bila tidak semua roll dicek.",
  impact="SPK QC 4-point tidak bisa ditutup sebelum jumlah ini tercapai.",
  example="min 2 · SPK 3 roll dengan sampling 30% → wajib 2 roll dicek",
  consumers=("services/inspection_service.py:sampling_rule",), related=("qc.sampling_pct",), risk="low")

# ═══════════════════════════════════════════════════════════════════════════
# TAMPILAN & NAVIGASI
# ═══════════════════════════════════════════════════════════════════════════
E("ui.show_coming_soon", group="sistem", section="menu", type="bool", default=True,
  scopes=("global",),
  label="Tampilkan grup menu 'Segera Hadir'",
  help="Menampilkan menu fitur yang belum aktif supaya tim tahu apa yang sedang disiapkan.",
  impact="Bila mati, grup 'Segera Hadir' hilang dari sidebar semua pengguna.",
  example="Mati → sidebar lebih ringkas, hanya menu yang sudah berfungsi",
  consumers=("App.js:buildNavGroups",), risk="low",
  sensitif_baca=False)

E("ui.coming_soon_collapsed", group="sistem", section="menu", type="bool", default=True,
  scopes=("global",),
  label="Grup 'Segera Hadir' awalnya tertutup",
  help="Menentukan apakah grup 'Segera Hadir' tampil tertutup saat aplikasi dibuka.",
  impact="Mengubah keadaan awal sidebar; pengguna tetap bisa membuka/menutup sendiri.",
  example="Aktif → grup tampil terlipat, hemat ruang layar",
  consumers=("config/navigationConfig.js:buildNavGroups",), risk="low",
  sensitif_baca=False)

# UAT 24 Okt (P12) — sorotan POS / katalog HP bisa dinyalakan & dimatikan per PT.
for _k, _label, _help in (   # KF-T4 — teks Lampiran A
    ("best_sellers", "tampilkan 'Produk Terlaris'", "Menampilkan deretan produk yang paling sering dipesan di layar kasir."),
    ("reorder", "tampilkan 'Sering dibeli pelanggan'", "Saat pelanggan dipilih, menampilkan barang yang pernah ia beli."),
    ("fbt", "Saran 'Sering dibeli bersama'",
     "Di keranjang, menampilkan barang yang sering dibeli bersamaan dengan isi keranjang."),
    ("featured", "tampilkan 'Produk Unggulan'",
     "Menampilkan produk yang ditandai MD atau manajer sebagai unggulan sampai tanggal akhirnya."),
    ("recommendation", "tampilkan 'Rekomendasi pelanggan'",
     "Saat pelanggan dipilih, menampilkan produk berstok yang mirip (desain, motif, atau kategori) dengan "
     "pembeliannya."),
):
    E(f"pos.{_k}.enabled", group="penjualan", section="saran-pos", type="bool", default=True,
      scopes=("global", "entity"), sensitif_baca=False,   # KF-T4 — dulu terbuka lewat kelompok Tampilan
      label=f"POS: {_label}", help=_help,
      impact="Bila mati, saran ini tidak tampil di kasir dan katalog HP.",
      example="Mati → kasir hanya melihat katalog biasa",
      consumers=("routers/pos.py", "services/pos_recommendation_service.py:highlights_config"), risk="low")
E("pos.best_sellers.window_days", group="penjualan", section="saran-pos", type="int", default=90, min=7, max=730, step=1, unit="hari",
  scopes=("global", "entity"),
  label="POS: Produk Terlaris dihitung dari (hari)",
  help="Hanya pesanan dalam sekian hari terakhir yang dihitung untuk menentukan Produk Terlaris.",
  impact="Mengubah urutan strip Produk Terlaris.",
  example="30 → terlaris 30 hari terakhir",
  consumers=("services/pos_recommendation_service.py:best_sellers",), risk="low",
  sensitif_baca=False)

# PR-T4 — halaman awal kini SIFAT PERAN (`permission_settings.role_traits.<peran>.home_view`, editor Peran & Hak Akses
# › Sifat peran) untuk semua peran bawaan & kustom; empat kunci lama tidak pernah dibaca layar → tidak dipakai.
for _role, _default_view, _label in (
    ("admin", "admin", "Admin"),
    ("manager", "reports", "Manajer"),
    ("sales", "sales", "Sales"),
    ("warehouse", "operations", "Gudang"),
):
    E(f"role_home.{_role}", group="sistem", section="menu", type="text", default=_default_view,
      sensitif_baca=True,   # KF-T1 — kelompok Tampilan terbuka untuk semua, beranda per peran tidak
      scopes=("global",),
      label=f"Halaman awal peran {_label}",
      help=f"Layar yang pertama dibuka ketika pengguna dengan peran {_label} masuk aplikasi.",
      impact="Mengubah halaman pendaratan setelah login untuk peran tersebut.",
      example=f"'{_default_view}' → {_label} langsung melihat layar tersebut setelah login",
      consumers=("permissions_config.py", "routers/admin.py"), risk="low",
      status="not_used", not_used_reason="Diatur per peran di Peran & Hak Akses › Halaman awal")


# ═══════════════════════════════════════════════════════════════════════════
# NOTIFIKASI & PEMBERITAHUAN  (FASE N)
# ═══════════════════════════════════════════════════════════════════════════
# Alamat notifikasi kini diturunkan dari WEWENANG (matriks izin), bukan dari nama peran
# yang diketik di titik kejadian — lihat `services/notification_audience.py`. Dua hal
# yang TIDAK bisa diturunkan dari izin dan karena itu jadi setelan pemilik:
#   (1) divisi/departemen mana yang ikut diberi tahu soal stok menipis (di banyak
#       perusahaan tekstil, MD/Merchandiser-lah yang memutuskan beli, bukan pemegang
#       izin PO — tetapi tidak semua perusahaan punya divisi itu);
#   (2) berapa hari sebuah tahap PO boleh mandek sebelum dianggap macet.
# Keduanya sengaja BERNILAI KOSONG/aman secara bawaan supaya tidak ada perusahaan yang
# tiba-tiba menerima pemberitahuan yang tidak diminta.

E("notif.low_stock_division", group="persetujuan", section="pemberitahuan", type="text", default="",
  scopes=("global",),   # KF-T3 (KF-10) — pindai stok tidak per PT: lapisan PT tidak pernah dibaca, jadi dicabut
  label="Departemen yang ikut diberi tahu stok tipis",
  help="Kosongkan bila cukup petugas pembelian saja. Bila diisi nama departemen (mis. Penjualan), semua karyawan "
       "departemen itu yang punya akun ikut menerima pemberitahuan stok menipis.",
  impact="Menambah penerima pemberitahuan stok menipis di luar petugas yang boleh membuat PO. Tidak pernah "
         "MENGURANGI penerima.",
  example="'Penjualan' → 3 karyawan departemen Penjualan yang punya akun ikut diberi tahu",
  consumers=("services/notification_service.py:generate_system_notifications",
             "services/notification_audience.py:resolve_recipients"), risk="low",
  ref="department")

E("notif.po_stage_stuck_days", group="persetujuan", section="pemberitahuan", type="duration", default=7,
  min=1, max=180, step=1, unit="hari", scopes=("global", "entity"),
  label="Tahap PO dianggap macet setelah (hari)",
  help="Bila sebuah tahap di Papan PO per Lini tidak ada kemajuan selama sekian hari, petugas pembelian diberi tahu.",
  impact="Ambang ini menentukan kapan pemberitahuan 'tahap PO macet' muncul. Angka "
         "kecil = lebih cepat mengingatkan, tetapi lebih berisik.",
  example="7 → tahap 'Tenun' yang mulai 8 hari lalu dan belum selesai akan diberitakan",
  consumers=("services/notification_service.py:_notify_stuck_po_stages",), risk="low")   # KF-T3 — dibaca per PT tiap PO

# ── KP-T7 (KP-09, KP-20, KP-21) — pengingat terjadwal: ambang dan penerima per PT ─────────────────────────────────────
# Dulu konstanta di `services/alert_service.py`, `alert_ops_service.py`, `escalation_service.py`, `wa_alert_service.py`,
# dan jalur pengingat lain. Bawaan = nilai yang berjalan sebelum unit ini (tidak ada pengingat yang berubah saat dipasang).
# Wewenang mengubah = izin `scheduler.configure` (izin yang menjaga seluruh pengaturan penjadwal; bawaan hanya Admin).
from services.reminder_policy import (  # noqa: E402 — pilihan editor tabel penerima
    BAWAAN_ESKALASI as _KPT7_ESKALASI, BAWAAN_PENERIMA as _KPT7_PENERIMA, MODE_LABEL as _KPT7_MODE,
    PENGINGAT as _KPT7_PENGINGAT, permission_options as _kpt7_izin, role_options as _kpt7_peran)

_KPT7 = {"permission": ("scheduler", "configure"), "risk": "low"}
_KPT7_PERAN = tuple(_kpt7_peran())

E("notif.ap_due_soon_days", group="notifikasi", section="tenggat-pengingat", type="duration", default=7, min=0, max=90, step=1, unit="hari",
  label="Ingatkan hutang jatuh tempo dalam (hari)",
  help="Tagihan pemasok yang jatuh tempo dalam sekian hari atau sudah lewat diingatkan. 0 = hanya yang sudah "
       "lewat jatuh tempo (dan jatuh tempo hari ini).",
  impact="Makin besar, makin awal tagihan diingatkan ke penerima pengingat hutang.",
  example="7 → tagihan yang jatuh tempo 5 hari lagi ikut diingatkan",
  consumers=("services/alert_service.py:job_ap_due",), **_KPT7)

E("notif.wo_released_stale_days", group="notifikasi", section="tenggat-pengingat", type="duration", default=3, min=1, max=90, step=1, unit="hari",
  label="Perintah kerja dirilis tertunda setelah",
  help="Umur perintah kerja berstatus dirilis yang belum selesai sebelum gudang diingatkan.",
  impact="Menentukan kapan perintah kerja dirilis masuk pengingat 'Perintah Kerja Produksi Tertunda'.",
  example="3 → perintah kerja yang dirilis 4 hari lalu dan belum selesai ikut diingatkan",
  consumers=("services/alert_service.py:job_production_stalled",), **_KPT7)

E("notif.wo_draft_stale_days", group="notifikasi", section="tenggat-pengingat", type="duration", default=7, min=1, max=180, step=1, unit="hari",
  label="Perintah kerja draf dianggap tertunda setelah",
  help="Umur draf perintah kerja yang belum dirilis sebelum gudang diingatkan.",
  impact="Menentukan kapan draf perintah kerja masuk pengingat 'Perintah Kerja Produksi Tertunda'.",
  example="7 → draf yang dibuat 8 hari lalu ikut diingatkan",
  consumers=("services/alert_service.py:job_production_stalled",), **_KPT7)

E("notif.warehouse_task_stale_days", group="notifikasi", section="tenggat-pengingat", type="duration", default=2, min=1, max=60, step=1,
  unit="hari",
  label="Tugas gudang dianggap tertunda setelah",
  help="Umur tugas barang masuk/keluar yang masih terbuka sebelum diringkas ke gudang.",
  impact="Menentukan kapan tugas gudang masuk pengingat 'Tugas Gudang Tertunda'.",
  example="2 → tugas yang dibuat 3 hari lalu dan masih terbuka ikut diringkas",
  consumers=("services/alert_service.py:job_ops_stalled",), **_KPT7)

E("notif.ar_due_soon_offsets", group="notifikasi", section="tenggat-pengingat", type="list", default=[-3, -1, 0, 1], unit="hari",
  label="Hari pengingat piutang terhadap jatuh tempo",
  help="Angka negatif = sebelum jatuh tempo, 0 = hari jatuh tempo, positif = sesudahnya. Tiap butir −30 sampai 30. "
       "Kosong = tidak ada pengingat piutang mendekati jatuh tempo.",
  impact="Menentukan pada hari apa saja pengingat piutang dikirim ke sales pemegang akun dan tim piutang.",
  example="[-7, 0] → pengingat dikirim 7 hari sebelum jatuh tempo dan pada hari jatuh tempo",
  consumers=("services/alert_ops_service.py:job_ar_due_soon",), **_KPT7)

E("notif.po_arrival_lookback_hours", group="notifikasi", section="tenggat-pengingat", type="int", default=24, min=1, max=168, step=1, unit="jam",
  label="Barang PO dianggap baru datang selama",
  help="Penerimaan barang PO yang selesai dalam jendela ini diberitakan oleh pemindai berkala.",
  impact="Jendela pendek mencegah berita lama terulang; jendela panjang menangkap penerimaan yang terlewat.",
  example="24 → penerimaan yang selesai 20 jam lalu masih diberitakan, yang 30 jam lalu tidak",
  consumers=("services/alert_ops_service.py:job_po_arrival",), **_KPT7)

E("notif.max_alerts_per_run", group="notifikasi", type="int", default=40, min=1, max=500, step=1,
  unit="peringatan", scopes=("global",),
  label="Paling banyak peringatan per sekali jalan",
  help="Pagar supaya satu pengingat tidak membanjiri kotak masuk. Berlaku untuk semua PT sekaligus.",
  impact="Peringatan di atas batas ini menunggu jalan berikutnya.",
  example="40 → bila 55 tagihan jatuh tempo, 40 diingatkan sekarang, sisanya di jalan berikutnya",
  consumers=("services/alert_service.py:job_ar_overdue", "services/alert_service.py:job_ap_due",
             "services/alert_service.py:job_budget_alert", "services/alert_service.py:job_production_stalled",
             "services/alert_ops_service.py:job_po_arrival", "services/alert_ops_service.py:job_backorder_ready",
             "services/alert_ops_service.py:job_ar_due_soon", "services/escalation_service.py:job_escalation_scan"),
  **_KPT7)

E("notif.turn_stale_days", group="notifikasi", section="tenggat-pengingat", type="duration", default=7, min=1, max=90, step=1, unit="hari",
  label="Jangan ingatkan giliran bila dokumen diam",
  help="Dokumen yang tidak bergerak lebih dari sekian hari tidak diingatkan ulang oleh pemindai giliran.",
  impact="Makin kecil, makin sedikit dokumen lama yang memunculkan pemberitahuan 'Giliran Anda'.",
  example="7 → pesanan yang terakhir berubah 10 hari lalu ditandai tanpa pemberitahuan",
  consumers=("services/turn_notification_service.py:scan",), **_KPT7)

E("notif.content_reminder_window_minutes", group="notifikasi", section="tenggat-pengingat", type="int", default=60, min=5, max=1440, step=5,
  unit="menit",
  label="Ingatkan tayang konten sebelum (menit)",
  help="Jarak sebelum jadwal tayang ketika PIC konten media sosial diingatkan.",
  impact="Makin besar, makin awal PIC diingatkan untuk menayangkan konten.",
  example="60 → konten yang dijadwalkan tayang 10.00 diingatkan sejak 09.00",
  consumers=("services/marketing_service.py:job_content_reminder",), **_KPT7)

E("notif.content_on_time_grace_minutes", group="notifikasi", section="tenggat-pengingat", type="int", default=60, min=0, max=1440, step=5,
  unit="menit",
  label="Toleransi tayang tepat waktu (menit)",
  help="Konten yang tayang dalam toleransi ini sesudah jadwalnya dihitung tepat waktu. 0 = tanpa toleransi.",
  impact="Mengubah angka 'tepat waktu' dan 'terlambat' di dasbor pemasaran.",
  example="60 → dijadwalkan 10.00, tayang 10.45 = tepat waktu; tayang 11.15 = terlambat",
  consumers=("services/marketing_ext.py:_toleransi_per_pt",), **_KPT7)

E("notif.campaign_budget_near_pct", group="notifikasi", section="tenggat-pengingat", type="pct", default=80, min=1, max=100, step=1, unit="%",
  label="Anggaran kampanye dianggap hampir habis pada",
  help="Persen realisasi anggaran kampanye yang memunculkan peringatan 'hampir habis'.",
  impact="Makin kecil, makin awal kampanye ditandai hampir habis.",
  example="80 → terpakai Rp8 jt dari Rp10 jt ditandai hampir habis",
  consumers=("services/marketing_cost_service.py:budget_summary",), **_KPT7)

E("notif.printer_stuck_minutes", group="notifikasi", section="tenggat-pengingat", type="int", default=30, min=5, max=1440, step=5, unit="menit",
  label="Label dianggap tertahan setelah (menit)",
  help="Lama antrean cetak label menunggu tanpa printer menyala di gudang itu sebelum diberitakan.",
  impact="Makin kecil, makin cepat kepala gudang dan manajer diberi tahu label tertahan.",
  example="30 → antrean yang menunggu 35 menit tanpa printer menyala diberitakan",
  consumers=("services/printer_stuck_watch.py:scan",), **_KPT7)

E("inventory.drift_critical_multiplier", group="keuangan-dasar", type="int", default=10, min=2, max=1000, step=1,
  unit="kali",
  label="Selisih persediaan kritis pada (× batas)",
  help="Kelipatan 'Selisih persediaan yang diperingatkan' yang menaikkan peringatan selisih persediaan menjadi "
       "kritis.",
  impact="Peringatan kritis tetap dikirim seketika (WhatsApp) walau mode pengiriman ringkasan.",
  example="10 × Rp1.000 = selisih Rp10.000 atau lebih ditandai kritis",
  consumers=("services/inventory_drift_watch.py:scan",), **_KPT7)

E("approval.reminder_max_listed", group="persetujuan", section="pemberitahuan", type="int", default=3, min=1, max=20, step=1, unit="dokumen",
  label="Dokumen yang disebut di pengingat persetujuan",
  help="Jumlah dokumen terlama yang ditulis nomornya di pengingat harian keputusan yang menunggu; sisanya diringkas "
       "'+N dokumen lain'.",
  impact="Makin besar, makin panjang isi pengingat harian.",
  example="3 → tiga dokumen terlama disebut, sisanya '+5 dokumen lain menunggu'",
  consumers=("services/approval_reminder.py:_ringkas",), **_KPT7)

E("rnd.design_due_soon_days", group="rnd", section="nilai-desainer", type="duration", default=3, min=1, max=30, step=1, unit="hari",
  label="Tenggat permintaan desain dekat dalam",
  help="Batas 'tenggat dekat' di ringkasan desainer (hari kalender, termasuk hari ini).",
  impact="Makin besar, makin banyak permintaan desain yang dihitung 'tenggat dekat'.",
  example="3 → tenggat lusa dihitung dekat, tenggat 5 hari lagi tidak",
  consumers=("services/design_request_service.py:summary",), **_KPT7)

E("notif.reminder_recipients", group="notifikasi", type="table", row_shape="list",
  default=[dict(r) for r in _KPT7_PENERIMA],
  label="Penerima tiap pengingat",
  help="Siapa yang menerima tiap pengingat terjadwal: peran yang dipilih, atau semua pemegang sebuah izin di PT itu. "
       "Tabel PT menggantikan tabel grup; pengingat yang tidak ada di tabel PT memakai baris grup, lalu bawaan. "
       "Piutang jatuh tempo dan penyusutan aset berlaku untuk semua PT sekaligus, jadi hanya mengikuti tabel grup.",
  impact="Mengubah kotak masuk siapa yang terisi pengingat itu. Penerima per izin dihitung saat pengingat dikirim.",
  example="Hutang pemasok jatuh tempo → semua pemegang izin bayar tagihan pemasok",
  columns=({"name": "reminder", "label": "Pengingat", "type": "enum", "default": "ap_due",
            "options": [{"value": k, "label": v} for k, v in _KPT7_PENGINGAT.items()]},
           {"name": "mode", "label": "Cara menentukan", "type": "enum", "default": "peran", "width": "170px",
            "options": [{"value": k, "label": v} for k, v in _KPT7_MODE.items()]},
           {"name": "roles", "label": "Peran", "type": "multi", "default": [], "options": list(_KPT7_PERAN),
            "options_source": "roles", "disabled_when": {"field": "mode", "equals": "izin"}},
           {"name": "permission", "label": "Izin", "type": "enum", "default": "",
            "options": _kpt7_izin(), "disabled_when": {"field": "mode", "equals": "peran"}}),
  consumers=("services/reminder_policy.py:recipients_for",), permission=("scheduler", "configure"), risk="medium")

E("notif.escalation_chain", group="notifikasi", type="table", row_shape="map", default=dict(_KPT7_ESKALASI),
  scopes=("global",),
  label="Naik ke siapa bila peringatan tidak ditindak",
  help="Peran penerima peringatan → peran di atasnya, dipakai eskalasi peringatan yang belum dibaca melewati batas "
       "waktu. 'all' = peringatan untuk semua; kosong = salinan per orang.",
  impact="Mengubah kotak masuk siapa yang menerima eskalasi.",
  example="gudang → manajer → admin",
  columns=({"name": "__key", "label": "Peran penerima", "type": "text"},
           {"name": "__value", "label": "Naik ke", "type": "enum", "options": list(_KPT7_PERAN),
            "options_source": "roles"}),
  consumers=("services/escalation_service.py:job_escalation_scan",), permission=("scheduler", "configure"),
  risk="medium")

E("notif.wa_broadcast_roles", group="notifikasi", type="list", default=["admin", "manager"], scopes=("global",),
  options=_KPT7_PERAN,
  label="Peran penerima WhatsApp pemberitahuan umum",
  help="Pemberitahuan yang ditujukan ke semua orang hanya dikirim lewat WhatsApp ke pemegang peran ini.",
  impact="Menambah atau mengurangi orang yang menerima WhatsApp pemberitahuan umum.",
  example="Admin dan Manajer → pemberitahuan umum masuk WhatsApp keduanya",
  consumers=("services/wa_alert_service.py:resolve_recipients",), **_KPT7)

E("notif.wa_pic_number", group="notifikasi", type="text", default="",
  label="Nomor WhatsApp PIC pengingat PT ini",
  help="Kosong = memakai nomor PIC di pengaturan WhatsApp. Bila diisi pada PT, pengingat PT itu dikirim ke nomor ini "
       "sebagai pengganti nomor PIC umum.",
  impact="PT yang mengisi menerima pengingatnya di nomor sendiri.",
  example="081234567890 → pengingat PT ini masuk ke nomor tersebut",
  consumers=("services/wa_alert_service.py:resolve_recipients",), **_KPT7)
# ── akhir blok KP-T7 ────────────────────────────────────────────────────────────────────────────────────────────────
