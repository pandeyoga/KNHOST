"""Tanya KN F0.5 — keputusan klien untuk asisten analitik (Rencana Bagian I §7)."""
from config_registry import E

_C = ("services/analytics_config.py:ai_policy",)

E("ai.sales_definition", group="sistem", section="tanya-kn", type="enum", default="net_order", scopes=("global",),
  options=({"value": "net_order", "label": "Pesanan bersih tanpa PPN, menurut tanggal pesanan"},
           {"value": "recognized", "label": "Pendapatan yang sudah diakui (saat barang dikirim)"}),
  label="Arti \u201cpenjualan\u201d bawaan",
  help="Arti kata “penjualan” atau “omzet” yang dipakai asisten bila pengguna tidak menyebut rinciannya.",
  impact="Mengubah angka bawaan di semua jawaban dan template penjualan.",
  example="Pesanan bersih → pesanan 24 Sep tetap dihitung 24 Sep walau dikirim 30 Sep",
  consumers=_C, risk="high")

E("ai.sales_attribution", group="sistem", section="tanya-kn", type="enum", default="team_split", scopes=("global",),
  options=({"value": "team_split", "label": "Tim sales di pesanan (dibagi % split), lalu sales pesanan"},
           {"value": "customer_owner", "label": "Sales penanggung jawab pelanggan"}),
  label="Penjualan dihitung milik sales yang mana",
  help="Menentukan siapa yang mendapat angka penjualan di peringkat sales dan pencapaian target: tim sales di "
       "pesanan (dibagi sesuai porsi) atau sales penanggung jawab pelanggan.",
  impact="Mengubah ranking sales, target vs realisasi, dan filter \u201cpenjualan saya\u201d.",
  example="Tim sales di pesanan → pesanan dengan porsi 60/40 dibagi ke dua sales",
  consumers=_C, risk="high")

# PR-T2 (K-47) — siapa yang memakai asisten / melihat margin / melihat nilai persediaan kini IZIN peran (`ai.view`,
# `ai.view_margin`, `ai.view_stock_value`); nilai tiga kunci di bawah dibaca sekali oleh migrasi pemasangan unit itu.
_PRT2_NOT_USED = "Diatur di Peran & Hak Akses › Asisten Tanya KN"

E("ai.margin_roles", group="sistem", section="tanya-kn", type="list", default=["admin", "manager"], scopes=("global",),
  label="Peran yang boleh melihat margin/laba kotor",
  help="Peran yang boleh melihat biaya pokok, laba kotor, dan margin lewat asisten. Peran lain menerima jawaban "
       "tanpa angka-angka itu.",
  impact="Menambah peran = peran itu melihat HPP lewat asisten.",
  example="Admin, Manajer → Sales bertanya margin → dijawab tanpa angka margin", consumers=_C, risk="high",
  status="not_used", not_used_reason=_PRT2_NOT_USED,
  items="roles")

E("ai.stock_value_roles", group="sistem", section="tanya-kn", type="list", default=["admin", "manager", "finance"],
  scopes=("global",),
  label="Peran yang boleh melihat nilai persediaan",
  help="Peran yang boleh melihat nilai rupiah persediaan lewat asisten. Peran lain hanya melihat jumlah dan "
       "banyaknya roll.",
  impact="Menambah peran = peran itu melihat nilai persediaan lewat asisten.",
  example="[admin, Manajer, finance]", consumers=_C, risk="medium",
  status="not_used", not_used_reason=_PRT2_NOT_USED,
  items="roles")

# ── Tanya KN F2 — chat bebas (mati sampai kunci OpenAI & persetujuan klien) ───
_CH = ("services/ai_chat_service.py:chat_config",)
_G = ("global",)
E("ai.enabled", group="sistem", section="tanya-kn", type="bool", default=False, scopes=_G,
  label="Aktifkan tanya-jawab bebas (AI)",
  help="Pertanyaan bebas dijawab layanan AI (OpenAI) memakai ringkasan angka, tanpa data pribadi. Laporan siap "
       "pakai tetap jalan tanpa ini.",
  impact="Aktif = pertanyaan dan ringkasan angka dikirim ke pihak luar; aktifkan hanya bila perusahaan "
         "menyetujuinya.",
  example="Mati → kotak tanya menyarankan template", consumers=_CH, risk="high")
E("ai.model_main", group="sistem", section="tanya-kn-teknis", type="text", default="gpt-6-sol", scopes=_G,
  label="Model AI untuk tanya-jawab", help="Nama model AI yang menjawab pertanyaan bebas. Bila model tidak "
                                           "tersedia, tanya-jawab gagal. Pengaturan teknis.",
  impact="Model tak tersedia → chat gagal.", example="gpt-6-sol", consumers=_CH, risk="medium")
E("ai.reasoning_effort", group="sistem", section="tanya-kn-teknis", type="enum", default="low", scopes=_G,
  options=({"value": "low", "label": "Rendah"}, {"value": "medium", "label": "Sedang"}),
  label="Ketelitian jawaban AI (bawaan)", help="Makin tinggi makin teliti, tetapi lebih mahal dan lebih lambat.",
  impact="Mengubah biaya per pertanyaan.", example="Rendah → jawaban lebih cepat dan murah", consumers=_CH, risk="low")
E("ai.deep_effort", group="sistem", section="tanya-kn-teknis", type="enum", default="medium", scopes=_G,
  options=({"value": "medium", "label": "Sedang"}, {"value": "high", "label": "Tinggi"}),
  label="Ketelitian “Analisis mendalam”", help="Dipakai saat pengguna menekan Analisis mendalam. Makin tinggi makin "
                                               "mahal.",
  impact="Mengubah biaya analisis mendalam.", example="Sedang → analisis mendalam lebih murah daripada Tinggi", consumers=_CH, risk="low")
E("ai.max_tool_rounds", group="sistem", section="tanya-kn-teknis", type="int", default=6, min=1, max=10, scopes=_G,
  label="Batas ambil data per pertanyaan (kali)", help="Berapa kali AI boleh mengambil data untuk satu pertanyaan. "
                                                       "Terlalu kecil membuat jawaban yang rumit terpotong.",
  impact="Terlalu kecil → jawaban kompleks terpotong.", example="6", consumers=_CH, risk="low",
  unit="kali")
E("ai.max_output_tokens", group="sistem", section="tanya-kn-teknis", type="int", default=4000, min=500, max=16000, scopes=_G,
  label="Batas panjang jawaban AI", help="Batas panjang jawaban AI. Terlalu kecil membuat jawaban terpotong. "
                                         "Pengaturan teknis.", impact="Terlalu kecil → jawaban terpotong.",
  example="4000", consumers=_CH, risk="low",
  unit="token")
E("ai.result_rows_to_model", group="sistem", section="tanya-kn-teknis", type="int", default=50, min=5, max=200, scopes=_G,
  label="Baris data yang dikirim ke AI", help="Jumlah baris hasil yang dikirim ke AI untuk dijelaskan; sisanya "
                                              "tetap ada di tabel dan unduhan. Lebih besar berarti biaya naik.",
  impact="Lebih besar = biaya naik.", example="50", consumers=_CH, risk="low",
  unit="baris")
E("ai.daily_question_limit", group="sistem", section="tanya-kn", type="int", default=60, min=1, max=1000, scopes=_G,
  label="Kuota pertanyaan harian per pengguna", help="Jumlah pertanyaan bebas per pengguna per hari. Laporan siap "
                                                     "pakai tidak dihitung; bila kuota habis pengguna diarahkan ke "
                                                     "laporan siap pakai.",
  impact="Habis → pengguna diarahkan ke template.", example="60", consumers=_CH, risk="low",
  unit="pertanyaan/hari")

# ── Tanya KN F2 sisa / F4 / F5 — biaya, peran, narasi, cache, routing, retensi ─
E("ai.model_fast", group="sistem", section="tanya-kn-teknis", type="text", default="gpt-6-luna", scopes=_G,
  label="Model AI untuk ringkasan singkat", help="Model AI yang menulis ringkasan 3–5 kalimat di atas grafik "
                                                 "laporan. Bila tidak tersedia, ringkasan dibuat otomatis dari "
                                                 "angka.",
  impact="Model tak tersedia → ringkasan jatuh ke ringkasan otomatis dari angka server.", example="gpt-6-luna",
  consumers=("services/ai_narrative.py:_ai_text",), risk="low")
E("ai.enabled_roles", group="sistem", section="tanya-kn", type="list",
  default=["admin", "manager", "sales_admin", "finance", "md", "warehouse_admin", "sales"], scopes=_G,
  label="Peran yang boleh memakai asisten", help="Peran yang boleh memakai Tanya KN. Admin selalu boleh; peran di "
                                                 "luar daftar tidak melihat menunya.",
  impact="Menghapus peran = peran itu kehilangan akses template, chat, dan jadwal.", example="[admin, Manajer, "
                                                                                             "sales]",
  consumers=("routers/ai_analytics.py:_ai_user",), risk="medium",
  status="not_used", not_used_reason=_PRT2_NOT_USED,
  items="roles")
E("ai.monthly_budget_usd", group="sistem", section="tanya-kn", type="int", default=100, min=0, max=100000, scopes=_G,
  label="Anggaran AI per bulan (USD)", help="Bila biaya bulan berjalan mencapai angka ini, tanya-jawab bebas dan "
                                            "ringkasan AI berhenti; laporan siap pakai tetap jalan. Isi 0 untuk "
                                            "mematikan seluruh AI berbayar.",
  impact="0 = AI berbayar selalu mati.", example="100", consumers=("services/ai_cost.py:budget_state",), risk="medium",
  unit="USD")
E("ai.template_cache_minutes", group="sistem", section="tanya-kn-teknis", type="int", default=5, min=0, max=120, scopes=_G,
  label="Simpan hasil laporan selama (menit)", help="Laporan yang sama tidak dihitung ulang selama sekian menit. "
                                                    "Isi 0 agar selalu dihitung ulang.",
  impact="0 = selalu hitung ulang.", example="5", consumers=("services/ai_templates.py:run",), risk="low",
  unit="menit")
E("ai.route_threshold_pct", group="sistem", section="tanya-kn-teknis", type="int", default=90, min=50, max=100, scopes=_G,
  label="Kemiripan pertanyaan agar pakai laporan", help="Pertanyaan yang mirip dengan laporan siap pakai setidaknya "
                                                        "sekian persen dijawab langsung dari laporan itu, tanpa AI.",
  impact="Terlalu rendah → pertanyaan berbeda salah diarahkan ke template.", example="90",
  consumers=("services/ai_chat_service.py:chat_events",), risk="low",
  unit="%")   # KF-T2 — dulu `ask` (tidak ada)
E("ai.chat_retention_days", group="sistem", section="tanya-kn-teknis", type="int", default=180, min=7, max=3650, scopes=_G,
  label="Riwayat percakapan disimpan selama (hari)", help="Percakapan yang tidak dibuka lagi lebih lama dari sekian "
                                                          "hari dihapus otomatis.",
  impact="Lebih kecil = riwayat lebih cepat hilang.", example="180", consumers=("services/ai_schedules.py:job_ai_maintenance",), risk="low",
  unit="hari")
E("ai.prewarm_enabled", group="sistem", section="tanya-kn-teknis", type="bool", default=False, scopes=_G,
  label="Siapkan AI tiap pagi agar lebih cepat", help="Tiap hari kerja pukul 06.55 sistem menyiapkan AI lebih dulu "
                                                      "agar pertanyaan pertama lebih cepat dan murah (sekitar Rp "
                                                      "330 per hari).",
  impact="Aktif = ± Rp 330 per pemanasan. Butuh kunci OpenAI & chat aktif.", example="Mati",
  consumers=("services/ai_chat_service.py:job_ai_prewarm",), risk="low")

# ── 2026-09-28 — kamus istilah & peringatan anomali ─────────────────────────
E("ai.glossary", group="sistem", section="tanya-kn", type="text", default="", scopes=_G,
  label="Kamus istilah perusahaan",
  help="Satu istilah per baris dengan format `istilah = arti`. Dikirim ke asisten agar memahami bahasa sehari-hari tim (mis. `bon = piutang pelanggan`, `gulungan = roll`).",
  impact="Istilah yang salah arti membuat asisten memilih metrik yang salah.",
  example="bon = piutang pelanggan\ngulungan = roll", consumers=("services/ai_chat_service.py:_glossary",), risk="low",
  value_format="multiline")
E("ai.anomaly_enabled", group="sistem", section="tanya-kn", type="bool", default=True, scopes=_G,
  label="Peringatan anomali otomatis",
  help="Tiap pagi 07.00 WIB memindai penjualan turun, piutang mulai macet, stok akan habis, dan PO terlambat, lalu mengirim notifikasi. Tanpa biaya AI.",
  impact="Mati = tab Peringatan tidak diperbarui otomatis.", example="Aktif",
  consumers=("services/ai_insights.py:job_ai_anomaly_scan",), risk="low")
E("ai.anomaly_drop_pct", group="sistem", section="tanya-kn", type="int", default=30, min=5, max=90, scopes=_G,
  label="Batas penurunan penjualan (%)",
  help="Seorang sales ditandai bila penjualannya 7 hari terakhir lebih rendah sekian persen dari rata-rata mingguan "
       "4 minggu sebelumnya.",
  impact="Terlalu kecil → terlalu banyak peringatan.", example="30 → rata-rata Rp 100 juta/minggu, minggu ini Rp 65 "
                                                               "juta → ditandai", consumers=("services/ai_insights.py:scan",), risk="low",
  unit="%")
E("ai.anomaly_cover_days", group="sistem", section="tanya-kn", type="int", default=14, min=1, max=90, scopes=_G,
  label="Batas stok akan habis (hari)",
  help="Produk ditandai bila stok tersedia hanya cukup untuk kurang dari sekian hari penjualan.",
  impact="Lebih besar = peringatan lebih awal tetapi lebih banyak.", example="14 → stok 100 yard, terjual 10 "
                                                                             "yard/hari (cukup 10 hari) → ditandai", consumers=("services/ai_insights.py:scan",), risk="low",
  unit="hari")
