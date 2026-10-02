"""Tanya KN F0.5 — keputusan klien untuk asisten analitik (Rencana Bagian I §7)."""
from config_registry import E

_C = ("services/analytics_config.py:ai_policy",)

E("ai.sales_definition", group="asisten-analitik", type="enum", default="net_order", scopes=("global",),
  options=({"value": "net_order", "label": "Pesanan bersih tanpa PPN, menurut tanggal pesanan"},
           {"value": "recognized", "label": "Pendapatan yang sudah diakui (saat barang dikirim)"}),
  label="Arti \u201cpenjualan\u201d bawaan",
  help="Dipakai asisten saat pengguna bertanya \u201cpenjualan\u201d atau \u201comzet\u201d tanpa keterangan.",
  impact="Mengubah angka bawaan di semua jawaban dan template penjualan.",
  example="net_order → pesanan 24 Sep tetap dihitung 24 Sep walau dikirim 30 Sep",
  consumers=_C, risk="high")

E("ai.sales_attribution", group="asisten-analitik", type="enum", default="team_split", scopes=("global",),
  options=({"value": "team_split", "label": "Tim sales di pesanan (dibagi % split), lalu sales pesanan"},
           {"value": "customer_owner", "label": "Sales penanggung jawab pelanggan"}),
  label="Kredit penjualan per sales",
  help="Menentukan siapa yang mendapat angka penjualan di ranking sales dan pencapaian target.",
  impact="Mengubah ranking sales, target vs realisasi, dan filter \u201cpenjualan saya\u201d.",
  example="team_split → pesanan dengan tim 60/40 dibagi ke dua sales",
  consumers=_C, risk="high")

E("ai.margin_roles", group="asisten-analitik", type="list", default=["admin", "manager"], scopes=("global",),
  label="Peran yang boleh melihat margin/laba kotor",
  help="Peran lain menerima jawaban tanpa HPP, laba kotor, maupun margin.",
  impact="Menambah peran = peran itu melihat HPP lewat asisten.",
  example="[admin, manager]", consumers=_C, risk="high")

E("ai.stock_value_roles", group="asisten-analitik", type="list", default=["admin", "manager", "finance"],
  scopes=("global",),
  label="Peran yang boleh melihat nilai persediaan",
  help="Peran lain hanya melihat qty dan jumlah roll, tanpa nilai rupiah stok.",
  impact="Menambah peran = peran itu melihat nilai persediaan lewat asisten.",
  example="[admin, manager, finance]", consumers=_C, risk="medium")

# ── Tanya KN F2 — chat bebas (mati sampai kunci OpenAI & persetujuan klien) ───
_CH = ("services/ai_chat_service.py:chat_config",)
_G = ("global",)
E("ai.enabled", group="asisten-analitik", type="bool", default=False, scopes=_G,
  label="Aktifkan chat bebas (OpenAI)",
  help="Pertanyaan bebas dijawab model OpenAI memakai data agregat hasil tool. Template laporan tetap jalan tanpa ini.",
  impact="Aktif = pertanyaan & hasil agregat dikirim ke OpenAI (tanpa data pribadi). Wajib persetujuan klien.",
  example="Mati → kotak tanya menyarankan template", consumers=_CH, risk="high")
E("ai.model_main", group="asisten-analitik", type="text", default="gpt-6-sol", scopes=_G,
  label="Model chat bebas", help="Nama model OpenAI (Responses API, function calling).",
  impact="Model tak tersedia → chat gagal.", example="gpt-6-sol", consumers=_CH, risk="medium")
E("ai.reasoning_effort", group="asisten-analitik", type="enum", default="low", scopes=_G,
  options=({"value": "low", "label": "low"}, {"value": "medium", "label": "medium"}),
  label="Tingkat penalaran bawaan", help="Makin tinggi makin teliti namun lebih mahal & lambat.",
  impact="Mengubah biaya per pertanyaan.", example="low", consumers=_CH, risk="low")
E("ai.deep_effort", group="asisten-analitik", type="enum", default="medium", scopes=_G,
  options=({"value": "medium", "label": "medium"}, {"value": "high", "label": "high"}),
  label="Penalaran \u201cAnalisis mendalam\u201d", help="Dipakai saat pengguna menekan Analisis mendalam.",
  impact="Mengubah biaya analisis mendalam.", example="medium", consumers=_CH, risk="low")
E("ai.max_tool_rounds", group="asisten-analitik", type="int", default=6, min=1, max=10, scopes=_G,
  label="Maks putaran tool per pertanyaan", help="Batas berapa kali model boleh mengambil data dalam satu pertanyaan.",
  impact="Terlalu kecil → jawaban kompleks terpotong.", example="6", consumers=_CH, risk="low")
E("ai.max_output_tokens", group="asisten-analitik", type="int", default=4000, min=500, max=16000, scopes=_G,
  label="Maks token jawaban", help="Batas panjang jawaban model.", impact="Terlalu kecil → jawaban terpotong.",
  example="4000", consumers=_CH, risk="low")
E("ai.result_rows_to_model", group="asisten-analitik", type="int", default=50, min=5, max=200, scopes=_G,
  label="Baris hasil yang dikirim ke model", help="Sisanya tetap tersedia di tabel & unduhan.",
  impact="Lebih besar = biaya naik.", example="50", consumers=_CH, risk="low")
E("ai.daily_question_limit", group="asisten-analitik", type="int", default=60, min=1, max=1000, scopes=_G,
  label="Kuota pertanyaan harian per pengguna", help="Hanya chat bebas; template tidak dihitung.",
  impact="Habis → pengguna diarahkan ke template.", example="60", consumers=_CH, risk="low")

# ── Tanya KN F2 sisa / F4 / F5 — biaya, peran, narasi, cache, routing, retensi ─
E("ai.model_fast", group="asisten-analitik", type="text", default="gpt-6-luna", scopes=_G,
  label="Model narasi singkat template", help="Dipakai untuk ringkasan 3–5 kalimat di atas grafik template (narasi 'luna').",
  impact="Model tak tersedia → ringkasan jatuh ke ringkasan otomatis dari angka server.", example="gpt-6-luna",
  consumers=("services/ai_narrative.py:narrate",), risk="low")
E("ai.enabled_roles", group="asisten-analitik", type="list",
  default=["admin", "manager", "sales_admin", "finance", "md", "warehouse_admin", "sales"], scopes=_G,
  label="Peran yang boleh memakai asisten", help="Admin selalu boleh. Peran lain di luar daftar tidak melihat Tanya KN.",
  impact="Menghapus peran = peran itu kehilangan akses template, chat, dan jadwal.", example="[admin, manager, sales]",
  consumers=("routers/ai_analytics.py:_ai_user",), risk="medium")
E("ai.monthly_budget_usd", group="asisten-analitik", type="int", default=100, min=0, max=100000, scopes=_G,
  label="Anggaran AI bulanan (USD)", help="Bila biaya bulan berjalan mencapai batas, chat bebas & narasi AI mati; template tetap jalan.",
  impact="0 = AI berbayar selalu mati.", example="100", consumers=("services/ai_cost.py:budget_state",), risk="medium")
E("ai.template_cache_minutes", group="asisten-analitik", type="int", default=5, min=0, max=120, scopes=_G,
  label="Cache hasil template (menit)", help="Template yang sama dengan parameter & hak akses sama tidak dihitung ulang. Periode tertutup disimpan 24 jam.",
  impact="0 = selalu hitung ulang.", example="5", consumers=("services/ai_templates.py:run",), risk="low")
E("ai.route_threshold_pct", group="asisten-analitik", type="int", default=90, min=50, max=100, scopes=_G,
  label="Ambang kemiripan pertanyaan → template (%)", help="Pertanyaan yang mirip template di atas ambang dijawab langsung sebagai template (tanpa model).",
  impact="Terlalu rendah → pertanyaan berbeda salah diarahkan ke template.", example="90",
  consumers=("services/ai_templates.py:route",), risk="low")
E("ai.chat_retention_days", group="asisten-analitik", type="int", default=180, min=7, max=3650, scopes=_G,
  label="Retensi riwayat percakapan (hari)", help="Sesi yang tidak diperbarui lebih lama dari ini dihapus oleh job pemeliharaan malam.",
  impact="Lebih kecil = riwayat lebih cepat hilang.", example="180", consumers=("services/ai_schedules.py:job_ai_maintenance",), risk="low")
E("ai.prewarm_enabled", group="asisten-analitik", type="bool", default=False, scopes=_G,
  label="Pemanasan cache prompt pagi", help="Hari kerja 06.55 WIB mengirim prefix statis ke OpenAI agar pertanyaan pertama lebih murah & cepat.",
  impact="Aktif = ± Rp 330 per pemanasan. Butuh kunci OpenAI & chat aktif.", example="Mati",
  consumers=("services/ai_chat_service.py:job_ai_prewarm",), risk="low")

# ── 2026-09-28 — kamus istilah & peringatan anomali ─────────────────────────
E("ai.glossary", group="asisten-analitik", type="text", default="", scopes=_G,
  label="Kamus istilah perusahaan",
  help="Satu istilah per baris dengan format `istilah = arti`. Dikirim ke asisten agar memahami bahasa sehari-hari tim (mis. `bon = piutang pelanggan`, `gulungan = roll`).",
  impact="Istilah yang salah arti membuat asisten memilih metrik yang salah.",
  example="bon = piutang pelanggan\ngulungan = roll", consumers=("services/ai_chat_service.py:_session_context",), risk="low")
E("ai.anomaly_enabled", group="asisten-analitik", type="bool", default=True, scopes=_G,
  label="Peringatan anomali otomatis",
  help="Tiap pagi 07.00 WIB memindai penjualan turun, piutang mulai macet, stok akan habis, dan PO terlambat, lalu mengirim notifikasi. Tanpa biaya AI.",
  impact="Mati = tab Peringatan tidak diperbarui otomatis.", example="Aktif",
  consumers=("services/ai_insights.py:job_ai_anomaly_scan",), risk="low")
E("ai.anomaly_drop_pct", group="asisten-analitik", type="int", default=30, min=5, max=90, scopes=_G,
  label="Ambang penurunan penjualan (%)",
  help="Sales ditandai bila penjualan 7 hari terakhir lebih rendah dari rata-rata mingguan 4 minggu sebelumnya sebesar persen ini.",
  impact="Terlalu kecil → terlalu banyak peringatan.", example="30", consumers=("services/ai_insights.py:scan",), risk="low")
E("ai.anomaly_cover_days", group="asisten-analitik", type="int", default=14, min=1, max=90, scopes=_G,
  label="Ambang stok akan habis (hari)",
  help="Produk ditandai bila stok tersedia hanya cukup untuk kurang dari sekian hari penjualan.",
  impact="Lebih besar = peringatan lebih awal tetapi lebih banyak.", example="14", consumers=("services/ai_insights.py:scan",), risk="low")
