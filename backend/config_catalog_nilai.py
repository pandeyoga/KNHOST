"""KF-T7 (KP-27, KP-28, CR-03) — nilai bisnis yang dulu ditulis mati di kode menjadi pengaturan.

Dulu konstanta di `ar_aging_service`, `customer_service`, `routers/sales_orders.py`, `special_order_phase2`,
`notification_service`, `stock_availability`, `stock_analytics_service`, `roll_service`, `supplier_dn_profile_service`,
`sample_sale_service`, `qc_inspection_service`, `gl_service`, `closing_service`, `inspection_service`,
`putaway_arrival_service`, `routers/auth.py`, `core_utils` (umur sesi), dan `esign_service`
(`docs/blueprint/unit/KF-T7.md`, Lampiran A butir #1–9, #45–52, #64–69). Bawaan = nilai yang berjalan sebelum unit ini,
jadi tidak ada perilaku yang berubah saat dipasang. Pembacanya: `services/nilai_pengaturan.py:nilai` (galat baca =
bawaan registry). Wewenang mengubah = `settings.manage`.

Tidak didaftarkan: `approval.special_order_min_amount` (butir #7) — ambang Rp10 jt pesanan khusus sudah dihapus KP-T4;
kapan pesanan khusus wajib disetujui kini dibaca dari Aturan Persetujuan (`approval_policy_service`, jenis
`special_order`), sehingga kunci kedua akan menjadi sumber kebenaran ganda.
"""
from config_registry import E

_G = ("global",)
_GE = ("global", "entity")
_P = {"permission": ("settings", "manage")}

# ── Kredit pelanggan (#1–4) — satu pembaca: `customer_service.credit_thresholds` ─────────────────────────────────────
_KREDIT = ("services/customer_service.py:credit_thresholds",)

E("ar.overdue_block_days", group="uang-masuk", section="kredit", type="duration", default=14, min=0, max=365, step=1,
  unit="hari", scopes=_GE,
  label="Blokir pelanggan bila telat lebih dari (hari)",
  help="Pelanggan tidak bisa membuat pesanan kredit baru bila tagihan tertuanya telat lebih dari angka ini. 0 = telat "
       "satu hari pun langsung diblokir.",
  impact="Status kredit pelanggan di umur piutang, kartu pelanggan, dan pemeriksaan kredit saat membuat pesanan berubah "
         "menjadi 'diblokir' lebih cepat (angka kecil) atau lebih lambat (angka besar).",
  example="14 → pelanggan yang tagihan tertuanya telat 10 hari berstatus peringatan; telat 15 hari diblokir",
  consumers=_KREDIT, related=("ar.credit_warning_pct",), **_P)

E("ar.credit_warning_pct", group="uang-masuk", section="kredit", type="pct", default=80, min=1, max=100, step=1,
  unit="%", scopes=_GE,
  label="Peringatkan saat piutang mencapai (% plafon)",
  help="Status pelanggan menjadi \"peringatan\" saat piutangnya mencapai persen ini dari plafon. 100 = hanya saat "
       "plafon penuh.",
  impact="Pelanggan berplafon diberi tanda peringatan lebih awal atau lebih lambat; pesanan tetap boleh dibuat.",
  example="80 → plafon Rp 10.000.000, piutang Rp 8.000.000 → peringatan; piutang Rp 7.000.000 → aktif",
  consumers=_KREDIT, related=("ar.overdue_block_days",), **_P)

# CR-T1 (K-27–K-29) — plafon bawaan PT untuk pelanggan yang belum punya plafon khusus di profil kredit. Bawaan 0 = tanpa
# batas (= perilaku hari ini: `customers.credit_limit` 0 berarti tanpa plafon). Diubah pemegang izin kredit
# (`credit_profile.approve`), bukan `settings.manage`. Satu pembaca: `credit_profile_service.effective`.
E("ar.default_credit_limit", group="uang-masuk", section="kredit", type="money", default=0, min=0,
  max=1000000000000, step=1000000, unit="Rp", scopes=_GE,
  label="Plafon bawaan pelanggan baru",
  help="Dipakai untuk pelanggan yang belum punya plafon khusus. 0 = tanpa batas.",
  impact="Mengisi angka membuat semua pelanggan tanpa plafon khusus mulai dibatasi.",
  example="Rp 25.000.000 · piutang Rp 26.000.000 → terblokir",
  consumers=("services/credit_profile_service.py:effective",), risk="high", requires_reason=True,
  permission=("credit_profile", "approve"), related=("ar.credit_warning_pct", "ar.overdue_block_days"))

# ── Penjualan (#5, #6, #8, #9, #51) ────────────────────────────────────────────────────────────────────────────────
E("sales.reservation_days", group="harga-diskon", section="alur-pesanan", type="duration", default=3, min=1, max=60,
  step=1, unit="hari", scopes=_GE,
  label="Masa reservasi stok pesanan (hari)",
  help="Pesanan yang belum disetujui melepas stok cadangannya setelah sekian hari.",
  impact="Berlaku untuk pesanan yang dibuat sesudah perubahan; pesanan lama tetap memakai tanggal kedaluwarsanya.",
  example="3 → pesanan dibuat Senin pukul 10.00 dan belum disetujui melepas stoknya Kamis pukul 10.00",
  consumers=("services/inventory_service.py:reservation_expires_at",), **_P)

# LB-T1 — Lapor Bayar CBD & DP: lama pesanan yang wajib bayar dulu menunggu bukti bayar sebelum tahannya jatuh tempo.
# Pembaca SATU-SATUNYA: `services/pay_hold_service.py:due_at` (dipanggil `start` saat tahan dimulai → `pay_hold.due_at`,
# tidak pernah dihitung ulang). Tanggal tersimpan itu dipakai (tanpa membaca pengaturan) oleh penyapu
# `inventory_service.expire_old_reservations` (LB-T5 — lewat batas tanpa laporan bayar menunggu → kedaluwarsa) dan
# pengingat `notification_service._notify_pay_due_soon` (H-1, jendela `notif.reservation_expiry_warn_hours`).
E("sales.batas_bayar_hari", group="harga-diskon", section="alur-pesanan", type="duration", default=3, min=1, max=30,
  step=1, unit="hari", scopes=_GE,
  label="Batas hari bayar pesanan wajib bayar dulu",
  help="Pesanan yang wajib bayar dulu (CBD atau uang muka) menunggu pembayaran sekian hari sejak disetujui.",
  impact="Lewat batas tanpa laporan bayar yang menunggu dicek, pesanan kedaluwarsa: stok dilepas dan uang yang sudah "
         "masuk menjadi titipan pelanggan. Berlaku untuk tahan bayar yang dibuat sesudah perubahan; tahan yang sudah "
         "berjalan tetap memakai batas lamanya.",
  example="3 → pesanan disetujui Senin pukul 10.00 dan belum dibayar jatuh tempo Kamis pukul 10.00",
  consumers=("services/pay_hold_service.py:due_at",), **_P)

E("sales.group_sales_max_members", group="harga-diskon", section="alur-pesanan", type="int", default=2, min=1, max=20,
  step=1, unit="orang", scopes=_GE,
  label="Maksimum anggota tim sales per pelanggan",
  help="Batas jumlah sales yang berbagi satu pelanggan atau satu pesanan (satu penanggung jawab ditambah rekan).",
  impact="Menyimpan tim sales di kartu pelanggan atau pesanan dengan anggota lebih banyak dari angka ini ditolak.",
  example="2 → satu penanggung jawab dan satu rekan; anggota ketiga ditolak",
  consumers=("services/customer_service.py:group_sales_max",), **_P)

E("sales.special_order_margin_pct", group="harga-diskon", section="pesanan-khusus", type="pct", default=30, min=0,
  max=500, step=1, unit="%", scopes=_GE,
  label="Margin bawaan pesanan khusus (%)",
  help="Dipakai menghitung usulan harga jual pesanan khusus bila margin tidak diisi. 0 = tanpa margin bawaan.",
  impact="Usulan harga jual pesanan khusus yang belum dikunci ikut berubah; harga yang sudah dikunci tidak berubah.",
  example="30 → harga pokok Rp 50.000 per meter → usulan harga jual Rp 65.000 per meter",
  consumers=("services/special_order_phase2.py:default_margin_pct",), **_P)

E("sales.special_order_multi_item_min", group="harga-diskon", section="pesanan-khusus", type="int", default=2, min=2,
  max=50, step=1, unit="barang", scopes=_G,
  label="Jumlah barang minimum pesanan multi-barang",
  help="Pesanan khusus dengan barang sebanyak ini atau lebih diperlakukan sebagai multi-barang: harganya dihitung per "
       "barang.",
  impact="Pesanan khusus dengan barang lebih sedikit dihitung harganya sebagai satu barang.",
  example="2 → pesanan khusus berisi dua barang dihitung harganya per barang",
  consumers=("services/special_order_phase2.py:multi_item_min",), **_P)

_KATALOG = ("services/sample_sale_service.py:catalogue_qty",)
E("sales.sample_catalogue_base_qty", group="harga-diskon", section="pesanan-khusus", type="decimal", default=1, min=0.1,
  max=100, step=0.1, unit="yard", scopes=_GE,
  label="Isi katalog sample per warna (yard)",
  help="Panjang kain per warna dalam satu katalog sample. Warna yang stok bebasnya kurang dari angka ini tidak ikut.",
  impact="Jumlah yang dipotong gudang dan ditagihkan untuk tiap warna katalog berubah untuk katalog baru.",
  example="1 → artikel dengan 12 warna tersedia → katalog 12 yard",
  consumers=_KATALOG, related=("sales.sample_catalogue_soft_qty",), **_P)

E("sales.sample_catalogue_soft_qty", group="harga-diskon", section="pesanan-khusus", type="decimal", default=2, min=0,
  max=100, step=0.1, unit="yard", scopes=_GE,
  label="Tambahan warna \"soft\" pada katalog (yard)",
  help="Ditagihkan sebagai komponen terpisah. 0 = tanpa tambahan.",
  impact="Jumlah tambahan untuk satu warna pilihan (soft) di katalog baru berubah.",
  example="2 → 12 warna × 1 yard + 2 yard warna soft = 14 yard",
  consumers=_KATALOG, related=("sales.sample_catalogue_base_qty",), **_P)

# ── Stok (#45–49, #66 putaway) ─────────────────────────────────────────────────────────────────────────────────────
E("inventory.low_stock_default_qty", group="stok-satuan", section="laris-lambat", type="decimal", default=100, min=0,
  max=1000000, step=1, unit="satuan dasar", scopes=_G,
  label="Stok dianggap menipis di bawah",
  help="Dipakai untuk barang tanpa titik pesan ulang saat memberi tahu stok menipis, dan sebagai batas \"Stok rendah\" "
       "di papan stok dan dasbor. 0 = barang tanpa titik pesan ulang tidak pernah diperingatkan dan tidak ada stok "
       "rendah.",
  impact="Pemberitahuan stok menipis ke bagian pembelian dan hitungan \"Stok rendah\" di dasbor ikut berubah.",
  example="100 → barang tanpa titik pesan ulang dengan stok tersedia 60 yard diperingatkan",
  consumers=("services/notification_service.py:generate_system_notifications",
             "services/stock_availability.py:low_stock_qty"), **_P)

_TREN = ("services/stock_analytics_service.py:trend_rules",)
E("inventory.stock_analytics.trend_window_days", group="stok-satuan", section="laris-lambat", type="duration",
  default=30, min=7, max=365, step=1, unit="hari", scopes=_GE,
  label="Jendela arah tren penjualan (hari)",
  help="Rata-rata penjualan sekian hari terakhir dibandingkan dengan rata-rata jendela laju jual untuk menentukan arah "
       "tren. Tidak bisa lebih panjang dari jendela laju jual.",
  impact="Arah tren (naik, stabil, turun) di Analitik Stok dihitung dari jendela yang lebih pendek atau lebih panjang.",
  example="30 → rata-rata 30 hari terakhir dibandingkan rata-rata 90 hari",
  consumers=_TREN, related=("inventory.stock_analytics.trend_band_pct",), **_P)

E("inventory.stock_analytics.trend_band_pct", group="stok-satuan", section="laris-lambat", type="pct", default=10,
  min=0, max=100, step=1, unit="%", scopes=_GE,
  label="Tren dianggap stabil dalam rentang (%)",
  help="Selisih di dalam rentang ini disebut \"stabil\". 0 = selisih sekecil apa pun disebut naik atau turun.",
  impact="Makin lebar rentangnya, makin banyak barang yang disebut stabil di Analitik Stok.",
  example="10 → rata-rata 30 hari 1,05 kali rata-rata 90 hari → stabil; 1,2 kali → naik",
  consumers=_TREN, related=("inventory.stock_analytics.trend_window_days",), **_P)

E("inventory.split_roll_max_length", group="stok-satuan", section="kerja-gudang", type="decimal", default=150, min=1,
  max=10000, step=1, unit="satuan dasar", scopes=_G,
  label="Panjang maksimum roll saat stok dipecah",
  help="Stok lama tanpa rincian roll dipecah menjadi roll sepanjang paling banyak angka ini saat rincian roll dibuat "
       "pertama kali.",
  impact="Hanya berlaku saat stok lama tanpa rincian roll diubah menjadi roll; roll yang sudah ada tidak berubah.",
  example="150 → stok tersedia 400 meter tanpa rincian roll → roll 150, 150, dan 100 meter",
  consumers=("services/roll_service.py:generate_rolls_from_balances",), **_P)

E("putaway.close_reason_min_chars", group="stok-satuan", section="kerja-gudang", type="int", default=10, min=1,
  max=200, step=1, unit="huruf", scopes=_G,
  label="Panjang minimum alasan menutup kedatangan",
  help="Alasan menutup sisa perintah simpan (roll yang belum tiba di rak) wajib sepanjang ini.",
  impact="Alasan yang lebih pendek ditolak saat menutup sisa perintah simpan.",
  example="10 → alasan \"roll hilang\" (11 huruf) diterima, \"hilang\" ditolak",
  consumers=("services/putaway_arrival_service.py:close_remaining",), **_P)

# ── Pengingat (#47) ────────────────────────────────────────────────────────────────────────────────────────────────
E("notif.reservation_expiry_warn_hours", group="notifikasi", section="tenggat-pengingat", type="int", default=24,
  min=1, max=168, step=1, unit="jam", scopes=_G,
  label="Ingatkan sebelum reservasi kedaluwarsa (jam)",
  help="Pemberitahuan dikirim bila reservasi akan kedaluwarsa dalam sekian jam. Kartu \"segera berakhir\" di dasbor "
       "pesanan memakai angka yang sama.",
  impact="Sales dan admin penjualan diingatkan lebih awal atau lebih dekat ke saat stok pesanan dilepas.",
  example="24 → pesanan yang reservasinya berakhir besok pukul 09.00 diingatkan sejak hari ini pukul 09.00",
  consumers=("services/notification_service.py:generate_system_notifications",
             "routers/sales_orders_extra.py:get_orders_stats"), **_P)

# ── Penerimaan barang (#50) ───────────────────────────────────────────────────────────────────────────────────────
_PROFIL = ("services/supplier_dn_profile_service.py:profile_rules",)
E("receiving.dn_profile_min_confirmed", group="penerimaan", section="menerima", type="int", default=3, min=1, max=50,
  step=1, unit="surat jalan", scopes=_G,
  label="Pakai format angka sesudah surat jalan dicek",
  help="Format angka surat jalan pemasok (titik atau koma sebagai pemisah ribuan) dipakai otomatis setelah sebanyak "
       "ini surat jalannya terkonfirmasi.",
  impact="Pembacaan surat jalan pemasok baru lebih cepat atau lebih lambat memakai format angka yang dipelajari.",
  example="3 → surat jalan keempat pemasok yang sama langsung dibaca dengan format angka pemasok itu",
  consumers=_PROFIL, related=("receiving.dn_profile_min_share_pct",), **_P)

E("receiving.dn_profile_min_share_pct", group="penerimaan", section="menerima", type="pct", default=80, min=1,
  max=100, step=1, unit="%", scopes=_G,
  label="Kesamaan format surat jalan minimum (%)",
  help="Format angka dipakai bila paling sedikit persen ini dari bukti pada surat jalan terkonfirmasi menunjukkan "
       "format yang sama.",
  impact="Makin tinggi, makin yakin sistem sebelum memakai format angka pemasok.",
  example="80 → 4 dari 5 bukti format Indonesia → format Indonesia dipakai",
  consumers=_PROFIL, related=("receiving.dn_profile_min_confirmed",), **_P)

# ── Mutu kain (#52, #66 inspeksi) ─────────────────────────────────────────────────────────────────────────────────
_TITIK = ("services/qc_inspection_service.py:interval_rules",)
E("qc.inspection_interval_yard", group="kualitas", section="inspeksi", type="decimal", default=15, min=1, max=500,
  step=1, unit="yard", scopes=_GE,
  label="Jarak antar titik inspeksi (yard)",
  help="Lembar inspeksi 4-point memuat satu titik tiap sekian yard.",
  impact="Jumlah kolom posisi cacat di lembar inspeksi berubah untuk inspeksi berikutnya; inspeksi lama tidak berubah.",
  example="15 → roll 200 yard diperiksa dalam 14 titik",
  consumers=_TITIK, related=("qc.inspection_min_points",), **_P)

E("qc.inspection_min_points", group="kualitas", section="inspeksi", type="int", default=10, min=1, max=100, step=1,
  unit="titik", scopes=_GE,
  label="Jumlah titik inspeksi minimum",
  help="Roll pendek tetap diperiksa sebanyak ini.",
  impact="Lembar inspeksi roll pendek memuat lebih banyak atau lebih sedikit kolom posisi cacat.",
  example="10 → roll 90 yard tetap diperiksa dalam 10 titik",
  consumers=_TITIK, related=("qc.inspection_interval_yard",), **_P)

E("qc.hold_reason_min_chars", group="kualitas", section="inspeksi", type="int", default=15, min=1, max=200, step=1,
  unit="huruf", scopes=_G,
  label="Panjang minimum alasan keputusan inspeksi",
  help="Alasan menolak barang, membuka ulang inspeksi, dan melepas atau menolak barang yang ditahan wajib sepanjang "
       "ini.",
  impact="Alasan yang lebih pendek ditolak; layar inspeksi menampilkan batas yang sama.",
  example="15 → \"warna beda dari sample\" (23 huruf) diterima, \"warna beda\" ditolak",
  consumers=("services/inspection_service.py:min_reason_len",), **_P)

# ── Pembukuan (#64, #65) ──────────────────────────────────────────────────────────────────────────────────────────
E("finance.rounding_tolerance_rupiah", group="keuangan-dasar", section="tutup-buku", type="money", default=1, min=0,
  max=1000, step=1, unit="Rp", scopes=_G, risk="high",
  label="Selisih yang dianggap pembulatan (Rp)",
  help="Selisih pencocokan nilai persediaan dengan pembukuan sampai angka ini ditandai sebagai pembulatan, bukan "
       "kesalahan. 0 = tidak ada toleransi.",
  impact="Layar pencocokan persediaan menyebut \"cocok\" atau \"pembulatan\" untuk selisih sampai angka ini.",
  example="1 → selisih Rp 0,40 ditandai pembulatan; selisih Rp 5 harus dijelaskan",
  consumers=("services/gl_service.py:inventory_reconciliation", "services/gl_service.py:inventory_drift_explain"),
  **_P)

E("periode.suspense_reason_min_chars", group="keuangan-dasar", section="tutup-buku", type="int", default=5, min=1,
  max=200, step=1, unit="huruf", scopes=_G,
  label="Panjang alasan melewati akun sementara",
  help="Berlaku saat tutup buku dipaksa walau akun sementara bersaldo.",
  impact="Alasan yang lebih pendek ditolak saat Admin memaksa tutup buku.",
  example="5 → alasan \"audit\" diterima, \"ok\" ditolak",
  consumers=("services/closing_service.py:suspense_reason_min_chars",), **_P)

# ── Keamanan akun & sesi (#67, #68) ───────────────────────────────────────────────────────────────────────────────
_SANDI = ("routers/auth.py:_register_failure",)
E("keamanan.maks_salah_sandi", group="keamanan", section="masuk", type="int", default=5, min=3, max=20, step=1,
  unit="kali", scopes=_G, risk="high",
  label="Salah sandi berturut-turut sebelum dikunci",
  help="Akun dikunci sementara setelah sandi salah sebanyak ini berturut-turut dari perangkat yang sama.",
  impact="Angka kecil lebih aman dari tebakan sandi, tetapi pengguna yang salah ketik lebih cepat terkunci.",
  example="5 → salah sandi kelima mengunci akun selama lama kunci",
  consumers=_SANDI, related=("keamanan.lama_kunci_menit",), **_P)

E("keamanan.lama_kunci_menit", group="keamanan", section="masuk", type="int", default=15, min=1, max=1440, step=1,
  unit="menit", scopes=_G, risk="high",
  label="Lama akun dikunci setelah salah sandi (menit)",
  help="Selama waktu ini akun yang terkunci tidak bisa masuk walau sandinya benar.",
  impact="Makin lama, makin sulit menebak sandi, tetapi pengguna menunggu lebih lama.",
  example="15 → terkunci pukul 08.00, bisa masuk lagi pukul 08.15",
  consumers=_SANDI, related=("keamanan.maks_salah_sandi",), **_P)

E("keamanan.umur_sesi_jam", group="keamanan", section="masuk", type="int", default=24, min=1, max=720, step=1,
  unit="jam", scopes=_G, risk="high",
  label="Lama sesi masuk berlaku (jam)",
  help="Sesudah itu pengguna diminta masuk lagi; sesi diperpanjang selama dipakai. Berlaku untuk sesi yang dibuat "
       "sesudah perubahan.",
  impact="Sesi yang sudah ada tetap pada lama berlakunya; sesi baru memakai angka ini.",
  example="24 → masuk Senin pukul 08.00 dan tidak dipakai lagi → diminta masuk lagi Selasa pukul 08.00",
  consumers=("routers/auth.py:login", "bootstrap.py:ensure_auth_indexes"), **_P)

# ── Tanda tangan elektronik (#69) ─────────────────────────────────────────────────────────────────────────────────
E("esign.otp_ttl_minutes", group="dokumen", section="tanda-tangan", type="int", default=10, min=1, max=60, step=1,
  unit="menit", scopes=_G,
  label="Masa berlaku kode tanda tangan (menit)",
  help="Kode yang dikirim ke penandatangan dokumen elektronik berlaku selama ini.",
  impact="Kode yang lebih tua ditolak dan penandatangan harus meminta kode baru.",
  example="10 → kode dikirim pukul 09.00 berlaku sampai pukul 09.10",
  consumers=("services/esign_service.py:create_request",), **_P)

E("esign.max_attempts", group="dokumen", section="tanda-tangan", type="int", default=5, min=1, max=20, step=1,
  unit="kali", scopes=_G,
  label="Batas salah kode tanda tangan",
  help="Permintaan tanda tangan dibatalkan setelah kode salah dimasukkan sebanyak ini.",
  impact="Penandatangan yang melewati batas harus meminta kode baru.",
  example="5 → salah kode kelima membatalkan permintaan tanda tangan",
  consumers=("services/esign_service.py:verify_and_sign",), **_P)
# ── akhir blok KF-T7 ───────────────────────────────────────────────────────────────────────────────────────────────
