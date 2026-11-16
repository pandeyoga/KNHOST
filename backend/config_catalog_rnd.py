"""FASE F — Katalog registry konfigurasi **R&D & DESAIN** (grup `rnd`).

Semua aturan alur R&D di sini bisa diubah pemilik lewat **Pusat Pengaturan** tanpa
deploy (INV-CFG-01/04). Kunci ber-prefix `rnd.` tersimpan di dokumen
`system_settings{scope:"global"}` dengan dot-path `rnd.<kunci>` dan mendukung
override per entitas — sesuai kemampuan `config_resolver`.

Bahasa label/help/impact SENGAJA awam: inilah teks yang dibaca pemilik usaha.
"""
from config_registry import E

G = ("global", "entity")

# Wewenang = izin `rnd.manage` (dipegang admin, manager, md) — KF-T1: tanpa jalur nama peran.
_RND_PERM = ("rnd", "manage")

# ═══════════════════════════════════════════════════════════════════════════
# KAPAN BARANG BOLEH DIPESAN / DIJUAL
# ═══════════════════════════════════════════════════════════════════════════
# KP-T4 — alasan baku kunci persetujuan yang pindah ke Aturan Persetujuan.
_KPT4_TIDAK_DIPAKAI = ("Dipindah ke Aturan Persetujuan (Pengaturan › Persetujuan › Aturan Persetujuan). Nilai terakhirnya hanya membentuk aturan bawaan selama aturan belum disimpan.")

E("rnd.lifecycle_enforcement", group="rnd", section="boleh-dijual", type="enum", default="block",
  options=({"value": "off", "label": "Abaikan (semua produk boleh dipesan)"},
           {"value": "warn", "label": "Peringatkan saja (tetap boleh lanjut)"},
           {"value": "block", "label": "Tolak (barang belum jadi tidak boleh dipesan)"}),
  scopes=G,
  label="Barang belum rilis boleh dipesan?",
  help="Menentukan apa yang terjadi bila barang hasil R&D yang belum sampai tahap produksi dipakai di pesanan "
       "penjualan atau pembelian: dibiarkan, diberi peringatan, atau ditolak.",
  impact="Pada 'Tolak', pembuatan SO/PR/PO atas barang yang belum dirilis akan gagal dengan "
         "pesan jelas. Produk lama (tanpa tahap tercatat) SELALU dianggap 'produksi' sehingga "
         "transaksi yang sudah berjalan tidak terpengaruh.",
  example="Sales mencoba menjual kain yang baru tahap labdip → ditolak, diminta menunggu rilis",
  consumers=("services/rnd_gate.py:policy",
             "services/rnd_gate.py:enforcement_mode"),
  related=("rnd.new_product_default_lifecycle",), risk="high", permission=_RND_PERM)

E("rnd.new_product_default_lifecycle", group="rnd", section="boleh-dijual", type="enum", default="produksi",
  options=({"value": "produksi", "label": "Produksi — langsung boleh dipesan/dijual"},
           {"value": "konsep", "label": "Konsep — wajib lewat alur R&D dulu"},
           {"value": "disetujui", "label": "Disetujui — menunggu rilis ke produksi"}),
  scopes=G,
  label="Tahap awal produk baru di Master Produk",
  help="Berlaku untuk produk yang dibuat langsung dari Master Produk (bukan hasil R&D). Bawaannya “Produksi”, "
       "artinya langsung boleh dijual.",
  impact="Bila diubah ke 'Konsep', setiap produk baru dari Master Produk TIDAK bisa langsung dijual sampai dirilis "
         "lewat R&D.",
  example="Diubah ke 'Konsep' → admin menambah produk baru, sales belum bisa menjualnya",
  consumers=("services/rnd_gate.py:default_new_lifecycle", "routers/products.py"),
  risk="medium", permission=_RND_PERM)

# MP-T1 (K-70, keputusan pemilik 16 Nov 2026) — produk hasil R&D baru boleh dirilis bila jalur beli/buatnya jelas.
E("rnd.release_requires_route", group="rnd", section="boleh-dijual", type="bool", default=True, scopes=G,
  label="Rilis produk wajib punya rute utama",
  help="Produk hasil R&D hanya bisa dirilis ke produksi bila artikelnya sudah punya rute utama di PT ini "
       "(beli dari pemasok, makloon per tahap, atau produksi sendiri).",
  impact="Bila dimatikan, produk bisa dirilis tanpa rute; pengadaan lalu tidak punya jalur bawaan dan SPK/PO diisi "
         "manual.",
  example="Kain printing baru belum diberi rute → tombol rilis ditolak sampai MD mengisi rute di Master Produk",
  consumers=("services/rnd_spec_service.py:release_product",),
  risk="medium", permission=_RND_PERM)

# ═══════════════════════════════════════════════════════════════════════════
# SUMBU VARIAN MASTER PRODUK (Warna × Grade × Asal — bisa diubah pemilik)
# ═══════════════════════════════════════════════════════════════════════════
E("rnd.variant_axes_default", group="rnd", section="boleh-dijual", type="list", default=["origin", "color", "grade", "customer", "lot"],
  scopes=G,
  label="Ciri pembeda barang yang disiapkan otomatis",
  help="Ciri pembeda (asal, warna, grade, pelanggan, lot) yang otomatis disiapkan saat MD membuat induk produk "
       "baru; urutannya menjadi urutan kode barang.",
  impact="Hanya memengaruhi induk BARU dan tombol atribut yang ditawarkan; induk yang sudah "
         "memiliki SKU tidak berubah strukturnya.",
  example="Warna, Grade, Asal → induk baru langsung punya Warna, Grade, Asal",
  consumers=("services/variant_axes.py:axis_config", "routers/product_media.py:meta"),
  related=("rnd.variant_axes_optional",), risk="medium", permission=_RND_PERM,
  items="options",
  ordered=True,
  options=[{"value": "origin", "label": "Asal (impor/lokal)"}, {"value": "color", "label": "Warna"}, {"value": "grade", "label": "Grade"}, {"value": "customer", "label": "Kode pelanggan"}, {"value": "lot", "label": "Lot"}, {"value": "size", "label": "Ukuran"}, {"value": "material", "label": "Bahan"}, {"value": "lebar", "label": "Lebar (cm)"}])

E("rnd.variant_axes_optional", group="rnd", section="boleh-dijual", type="list", default=[], scopes=G,
  label="Ciri pembeda tambahan yang boleh dipakai",
  help="Ciri pembeda yang tidak dipasang otomatis tetapi boleh ditambahkan MD untuk induk tertentu (mis. ukuran, "
       "bahan, lebar).",
  impact="Menambah kode di sini memunculkan tombol atribut tambahan di form induk produk.",
  example="Lebar (cm) → MD bisa menambah ciri Lebar untuk induk tertentu",
  consumers=("services/variant_axes.py:axis_config",),
  related=("rnd.variant_axes_default",), risk="low", permission=_RND_PERM,
  items="options",
  options=[{"value": "origin", "label": "Asal (impor/lokal)"}, {"value": "color", "label": "Warna"}, {"value": "grade", "label": "Grade"}, {"value": "customer", "label": "Kode pelanggan"}, {"value": "lot", "label": "Lot"}, {"value": "size", "label": "Ukuran"}, {"value": "material", "label": "Bahan"}, {"value": "lebar", "label": "Lebar (cm)"}])

# ═══════════════════════════════════════════════════════════════════════════
# SIAPA BERWENANG
# ═══════════════════════════════════════════════════════════════════════════
E("rnd.spec_approval_roles", group="rnd", section="boleh-dijual", type="list", default=["manager", "admin"],
  scopes=G,
  label="Siapa menyetujui spesifikasi & rilis produk",
  help="Peran yang berhak menyetujui spesifikasi R&D sehingga produk lahir, dan merilisnya ke produksi.",
  impact="Peran di luar daftar akan ditolak walaupun mencoba lewat API langsung.",
  example="['Manajer','admin'] → sales boleh mengajukan, tidak boleh menyetujui",
  consumers=("services/approval_policy_service.py:default_rows_for",),
  risk="high", permission=_RND_PERM,
  # KP-T4 — isi kunci ini pindah ke tabel kebijakan persetujuan (`approval_policies`).
  status="not_used", not_used_reason=_KPT4_TIDAK_DIPAKAI,
  items="roles")

# 23 Okt — selaras keputusan pemilik UAT v3 (22 Okt): pemenang boleh diputus Manajer ATAU MD. Matriks `sample_acc`
# (config_divisions) sudah memuat md, tetapi lapis kebijakan ini masih bawaan lama → MD tetap ditolak di server.
E("rnd.sample_decision_roles", group="rnd", section="sample", type="list", default=["manager", "md", "admin"],
  scopes=G,
  label="Siapa memilih pemasok pemenang sample",
  help="Peran yang berhak memutuskan pemasok pemenang sample. Keputusan ini membentuk kontrak harga yang dipakai "
       "PO, jadi wewenangnya dibatasi.",
  impact="Peran di luar daftar tidak bisa memutus, sehingga tidak bisa membentuk kontrak harga.",
  example="['Manajer','md','admin'] → MD/Manajer memutus; ['Manajer','admin'] → staf R&D menilai, Manajer memutus",
  consumers=("services/approval_policy_service.py:default_rows_for",),
  risk="high", permission=_RND_PERM,
  # KP-T4 — isi kunci ini pindah ke tabel kebijakan persetujuan (`approval_policies`).
  status="not_used", not_used_reason=_KPT4_TIDAK_DIPAKAI,
  items="roles")

# ═══════════════════════════════════════════════════════════════════════════
# ITERASI SAMPLE (rnd 1 → 2 → 3 …)
# ═══════════════════════════════════════════════════════════════════════════
E("rnd.max_rounds", group="rnd", section="sample", type="int", default=3, min=1, max=10, step=1,
  unit="kali", scopes=G,
  label="Batas ulang sample per pemasok (kali)",
  help="Berapa kali satu pemasok boleh mengirim ulang sample sebelum butuh izin khusus dari Manajer/admin dengan "
       "alasan tertulis.",
  impact="Melewati batas hanya bisa dibuka Manajer/admin DENGAN alasan tertulis — supaya biaya & waktu sample tidak "
         "lepas kendali tanpa jejak.",
  example="Batas 3 → putaran ke-4 wajib alasan dari Manajer",
  consumers=("services/rnd_sample_service.py:open_round",), risk="medium",
  permission=_RND_PERM)

E("rnd.round_sla_days", group="rnd", section="sample", type="duration", default=7, min=1, max=90, step=1,
  unit="hari", scopes=G,
  label="Target hari tiap putaran sample",
  help="Dipakai menghitung tenggat tiap putaran sample. Putaran yang disetor melewati tenggat ditandai terlambat.",
  impact="Mengubah angka ini mengubah tenggat putaran BARU (putaran yang sudah jalan tidak berubah).",
  example="7 hari → permintaan dikirim 1 Agu, tenggat 8 Agu",
  consumers=("services/rnd_sample_service.py:send_sample",
             "services/rnd_sample_service.py:open_round"),
  risk="low", permission=_RND_PERM)

E("rnd.require_attachment_on_round", group="rnd", section="sample", type="bool", default=True, scopes=G,
  label="Wajib lampiran & catatan saat setor hasil",
  help="Bila aktif, hasil sample tidak bisa disetor tanpa mengunggah bukti (foto hasil, gambar desain, atau hasil "
       "ukur) dan menulis penjelasan.",
  impact="Mematikan ini membuat riwayat R&D kehilangan bukti — penilaian jadi tidak bisa diaudit.",
  example="Aktif → tombol 'Setor Hasil' menolak bila belum ada berkas terunggah",
  consumers=("services/rnd_sample_service.py:submit_round",), risk="high",
  permission=_RND_PERM)

E("rnd.require_design_for_proofing", group="rnd", section="sample", type="bool", default=True, scopes=G,
  label="Proofing wajib merujuk kode desain",
  help="Sample printing (proofing) harus menunjuk desain/pattern ber-kode dari Master Desain, "
       "bukan nama motif yang diketik bebas.",
  impact="Mematikan ini membuat hasil proofing tidak bisa ditelusuri ke artwork mana pun.",
  example="Aktif → permintaan proofing tanpa desain ditolak dengan pesan jelas",
  consumers=("services/rnd_gate.py:policy",), risk="medium",
  permission=_RND_PERM)

# UAT 24 Okt (P4.2, P4.3) — urutan produk baru & labdip multi-warna.
E("rnd.require_stage_chain", group="rnd", section="sample", type="bool", default=True, scopes=G,
  label="Produk baru wajib urut: handfeel → labdip",
  help="Labdip produk baru harus merujuk sample handfeel yang sudah disetujui, dan proofing harus memakai kain "
       "dasar yang sudah lolos. Uji ulang barang lama tidak terkena aturan ini.",
  impact="Mati → labdip/proofing boleh dibuat tanpa tahap sebelumnya (perilaku lama).",
  example="Aktif → labdip tanpa handfeel ACC ditolak dengan petunjuk memilih handfeel induk",
  consumers=("services/rnd_gate.py:policy",), risk="medium",
  permission=_RND_PERM)

E("rnd.labdip_max_colors", group="rnd", section="sample", type="int", default=10, min=1, max=30, step=1, unit="warna", scopes=G,
  label="Batas warna per permintaan labdip",
  help="Satu permintaan labdip boleh menguji banyak warna sekaligus; tiap warna jadi satu sample (putaran, ACC, "
       "pemenang & spesifikasi sendiri) dalam satu kelompok.",
  impact="Menentukan jumlah warna maksimum yang bisa diisi di form labdip.",
  example="10 → labdip 5 warna dibuat sebagai 5 sample berkelompok",
  consumers=("services/rnd_gate.py:policy",), risk="low", permission=_RND_PERM)

# ═══════════════════════════════════════════════════════════════════════════
# DESIGN STUDIO — KODE OTOMATIS & AMBANG NILAI
# ═══════════════════════════════════════════════════════════════════════════
E("rnd.design_code_pattern", group="rnd", section="kode-desain", type="text", default="{DESIGNER}-{CAT}-{DCAT}-{SEQ}",
  scopes=G, label="Pola kode desain otomatis",
  help="Kode desain dibentuk otomatis saat desain dibuat. Placeholder: {DESIGNER} = inisial desainer (mis. SRI), "
       "{CAT} = kode Kategori Pattern (mis. SLR), {DCAT} = kode Kategori Design (AO/PG), {ENTITY} = prefix PT, "
       "{SEQ} = nomor urut. {TYPE} (jenis desain lama) masih dikenali untuk desain lawas.",
  impact="Mengubah pola hanya berlaku untuk desain BARU; kode lama tidak berubah.",
  example="{DESIGNER}-{CAT}-{DCAT}-{SEQ} → SRI-SLR-AO-001",
  consumers=("services/design_studio_service.py:code_config",), risk="low",
  permission=_RND_PERM)

E("rnd.design_code_seq_digits", group="rnd", section="kode-desain", type="int", default=3, min=2, max=6, step=1,
  scopes=G, label="Jumlah digit nomor urut kode desain",
  help="Panjang nomor urut di akhir kode desain (3 → 001, 4 → 0001).",
  impact="Berlaku untuk desain baru saja.", example="3 → BDI-PTR-SLR-001",
  consumers=("services/design_studio_service.py:code_config",), risk="low",
  permission=_RND_PERM,
  unit="digit")

E("rnd.design_prefix_motif", group="rnd", section="kode-desain", type="text", default="MTF", scopes=G,
  label="Awalan kode desain jenis Motif", help="Singkatan jenis “motif” di kode desain. Berlaku untuk desain baru "
                                               "saja.",
  impact="Berlaku untuk desain baru saja.", example="MTF → kode desain SRI-MTF-001",
  consumers=("services/design_studio_service.py:code_config",), risk="low",
  permission=_RND_PERM)

E("rnd.design_prefix_pattern", group="rnd", section="kode-desain", type="text", default="PTR", scopes=G,
  label="Awalan kode desain jenis Pattern", help="Singkatan jenis “pattern” di kode desain. Berlaku untuk desain "
                                                 "baru saja.",
  impact="Berlaku untuk desain baru saja.", example="PTR",
  consumers=("services/design_studio_service.py:code_config",), risk="low",
  permission=_RND_PERM)

E("rnd.design_prefix_artwork", group="rnd", section="kode-desain", type="text", default="ART", scopes=G,
  label="Awalan kode desain jenis Artwork", help="Singkatan jenis “artwork” di kode desain. Berlaku untuk desain "
                                                 "baru saja.",
  impact="Berlaku untuk desain baru saja.", example="ART",
  consumers=("services/design_studio_service.py:code_config",), risk="low",
  permission=_RND_PERM)

E("rnd.design_acc_min_score", group="rnd", section="kode-desain", type="decimal", default=1.5, min=0, max=2, step=0.25,
  scopes=G, label="Nilai minimum agar versi desain disetujui",
  help="Tiap versi desain dinilai pada skala 0–2. Versi hanya bisa disetujui bila nilainya mencapai angka ini.",
  impact="Menaikkan ambang membuat lebih banyak versi harus direvisi sebelum ACC.",
  example="1,5 → versi bernilai 1,25 wajib revisi",
  consumers=("services/design_studio_service.py:code_config",), risk="medium",
  permission=_RND_PERM,
  unit="poin")

# ═══════════════════════════════════════════════════════════════════════════
# PS-18 — ESKALASI SLA OTOMATIS (round yang lewat tenggat tidak boleh diam)
# ═══════════════════════════════════════════════════════════════════════════
E("rnd.sla_escalate_admin_days", group="rnd", section="sample", type="duration", default=3, min=1, max=30,
  step=1, unit="hari", scopes=G,
  label="Putaran terlambat naik ke pemilik setelah",
  help="Putaran sample yang lewat tenggat diberitahukan ke Manajer setiap hari; bila terlambatnya sudah mencapai "
       "sekian hari, pemberitahuan juga dikirim ke admin/pemilik.",
  impact="Angka lebih kecil = pemilik lebih cepat tahu tetapi notifikasi lebih sering. Angka lebih besar = lebih "
         "tenang tetapi keterlambatan bisa lama tak terlihat. Pengiriman disaring sekali per hari per putaran, jadi "
         "tidak pernah dobel.",
  example="3 hari → terlambat 2 hari: hanya Manajer. Terlambat 3 hari: Manajer + admin",
  consumers=("services/rnd_gate.py:policy",),
  related=("rnd.round_sla_days",), risk="low", permission=_RND_PERM)

# ═══════════════════════════════════════════════════════════════════════════
# PS-18 — BOBOT NILAI (GRADE) KINERJA DESAINER
# Grade dihitung sendiri dari jejak round; bobot di bawah menentukan apa yang
# PALING dinilai. Bila satu komponen belum punya data, bobotnya dinormalkan ulang
# (desainer baru tidak langsung jatuh ke grade D karena datanya belum lengkap).
# Keputusan pemilik K-08 (26 Okt) — keempat bobot (tepat waktu + skor + ACC + nilai
# versi desain) adalah porsi dari 100%; nilai versi desain BUKAN bonus. Bawaan
# 40/40/20/20 (= 120, dinormalkan jadi 33,3/33,3/16,7/16,7) diganti 30/30/20/20 (= 100).
# Bila pemilik menyimpan bobot yang jumlahnya bukan 100, `compute_grade` tetap
# menyetarakannya ke 100% (Σ bobot × komponen ÷ Σ bobot) dan layar menyebutnya.
# ═══════════════════════════════════════════════════════════════════════════
E("rnd.kpi_weight_on_time", group="rnd", section="nilai-desainer", type="pct", default=30, min=0, max=100, step=5,
  unit="%", scopes=G,
  label="Nilai desainer: bobot tepat waktu",
  help="Seberapa besar “menepati tenggat” menentukan nilai akhir desainer. Keempat bobot nilai desainer berjumlah "
       "100%. Isi 0 = aspek ini tidak ikut menentukan nilai.",
  impact="Menaikkan angka ini membuat desainer yang cepat & tepat waktu naik peringkat; "
         "menurunkannya membuat mutu/skor penilaian lebih dominan.",
  example="30% → desainer dengan on-time 100% mendapat 30 dari 100 poin dari komponen ini",
  consumers=("services/rnd_gate.py:policy",),
  related=("rnd.kpi_weight_score", "rnd.kpi_weight_acc"), risk="low",
  permission=_RND_PERM)

E("rnd.kpi_weight_score", group="rnd", section="nilai-desainer", type="pct", default=30, min=0, max=100, step=5,
  unit="%", scopes=G,
  label="Nilai desainer: bobot skor Manajer",
  help="Seberapa besar rata-rata skor yang diberi Manajer saat menilai hasil (0–100) menentukan nilai akhir "
       "desainer.",
  impact="Menaikkan angka ini membuat mutu hasil lebih menentukan daripada kecepatan.",
  example="30% → rata-rata skor 90 memberi 27 dari 100 poin",
  consumers=("services/rnd_gate.py:policy",),
  related=("rnd.kpi_weight_on_time",), risk="low", permission=_RND_PERM)

E("rnd.kpi_weight_acc", group="rnd", section="nilai-desainer", type="pct", default=20, min=0, max=100, step=5,
  unit="%", scopes=G,
  label="Nilai desainer: bobot sekali jadi",
  help="Seberapa besar porsi hasil yang langsung disetujui (tanpa revisi) menentukan nilai akhir desainer. Isi 0 = "
       "aspek ini tidak ikut menentukan nilai.",
  impact="Menaikkan angka ini menghargai desainer yang hasilnya 'sekali jadi'.",
  example="20% → dari 10 putaran dinilai, 8 ACC → 16 dari 100 poin",
  consumers=("services/rnd_gate.py:policy",),
  related=("rnd.kpi_weight_on_time",), risk="low", permission=_RND_PERM)

E("rnd.kpi_weight_design", group="rnd", section="nilai-desainer", type="pct", default=20, min=0, max=100, step=5,
  unit="%", scopes=G,
  label="Nilai desainer: bobot nilai desain",
  help="Seberapa besar rata-rata nilai versi desain (skala 0–2) menentukan nilai akhir desainer. Bagian dari 100%, "
       "bukan tambahan.",
  impact="0 = nilai desain hanya ditampilkan, tidak mengubah grade. Menaikkan angka ini membuat mutu karya desain "
         "ikut menentukan peringkat, bukan hanya putaran sample.",
  example="20% → rata nilai desain 1,5/2 (=75) memberi 15 dari 100 poin",
  consumers=("services/rnd_kpi_service.py:designer_kpi",),
  related=("rnd.kpi_weight_score", "rnd.design_acc_min_score"), risk="low",
  permission=_RND_PERM)

E("rnd.kpi_penalty_rework", group="rnd", section="nilai-desainer", type="decimal", default=0.3, min=0, max=2,
  step=0.1, scopes=G,
  label="Nilai desainer: potongan kerja ulang",
  help="Pengurang nilai untuk tiap 1% hasil yang harus diulang (revisi atau ditolak). 0 berarti tidak mengurangi "
       "nilai. Isi 0 = tanpa pengurang.",
  impact="0 = pengulangan tidak mengurangi nilai. 0,3 = rework 50% memotong 15 poin.",
  example="0,3 dengan rework 40% → nilai dipotong 12 poin",
  consumers=("services/rnd_gate.py:policy",),
  related=("rnd.kpi_penalty_overdue",), risk="low", permission=_RND_PERM,
  unit="poin per 1%")

E("rnd.kpi_penalty_overdue", group="rnd", section="nilai-desainer", type="decimal", default=0.3, min=0, max=2,
  step=0.1, scopes=G,
  label="Nilai desainer: potongan terlambat",
  help="Pengurang nilai untuk tiap 1% hasil yang terlambat. 0 berarti keterlambatan tidak mengurangi nilai. Isi 0 = "
       "tanpa pengurang.",
  impact="0 = keterlambatan tidak mengurangi nilai (hanya tampil sebagai angka). "
         "0,3 = sepertiga dari persentase keterlambatan dipotong dari nilai.",
  example="0,3 dengan 30% putaran terlambat → nilai dipotong 9 poin",
  consumers=("services/rnd_gate.py:policy",),
  related=("rnd.kpi_penalty_rework", "rnd.sla_escalate_admin_days"), risk="low",
  permission=_RND_PERM,
  unit="poin per 1%")

# ═══════════════════════════════════════════════════════════════════════════
# HILIR: KONTRAK & BAHAN SAMPLE
# ═══════════════════════════════════════════════════════════════════════════
E("rnd.auto_contract_on_decide", group="rnd", section="sample", type="bool", default=True, scopes=G,
  label="Pemenang sample langsung jadi kontrak harga",
  help="Bila aktif, memilih pemasok pemenang otomatis membuat kontrak pemasok (harga, jumlah pesan minimum, lama "
       "kirim) dengan nomor sample sebagai rujukan.",
  impact="Mematikan ini membuat harga hasil sample harus diinput ulang manual di kontrak — "
         "risiko harga PO tidak sesuai kesepakatan sample.",
  example="Aktif → keputusan sample SMP-00002 menghasilkan kontrak KSC/SCT-00007",
  consumers=("services/rnd_sample_service.py:decide_sample",), risk="high",
  permission=_RND_PERM)

E("rnd.sample_material_from_stock", group="rnd", section="sample", type="bool", default=True, scopes=G,
  label="Ambil bahan sample mengurangi stok gudang",
  help="Bila aktif, kain yang diambil untuk membuat sample langsung mengurangi stok gudang, sehingga stok di sistem "
       "sama dengan stok fisik.",
  impact="Mematikan ini membuat pengambilan bahan sample tidak tercatat, sehingga stok "
         "sistem lebih besar daripada stok fisik.",
  example="Ambil 3 meter untuk labdip → sisa roll berkurang 3 meter, biaya sample tercatat",
  consumers=("services/rnd_gate.py:policy",), risk="high",
  permission=_RND_PERM)
