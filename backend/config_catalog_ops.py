"""FASE G-0 — Katalog registry konfigurasi: kebijakan OPERASIONAL per modul.

Entri di sini tersimpan pada dokumen `system_settings` dengan scope tersendiri
(`uom` · `lot` · `makloon` · `receiving` · `hr`) — bukan di dokumen `global`.
`config_registry.legacy_target()` memetakannya otomatis dari prefix kunci.

CATATAN KEJUJURAN SCOPE (diperbarui FASE E-4 · E4.5): dulu `scopes` di sini sengaja
hanya `("global",)` karena mesin pembacanya belum mendukung override per badan usaha —
menuliskan scope yang tidak dihormati mesin sama dengan membuat "tombol palsu".
Sejak E4.5 mesinnya SUDAH mendukung: `get_settings(entity_id)` /
`hr_service.get_hr_settings(entity_id)` menimpa nilai global dengan
`config_resolver.entity_overlay(<scope>, entity_id)`. Karena itu `scopes` sekarang
`("global", "entity")` — dan itu jujur, bukan aspiratif.

Keputusan pemilik #6 yang mendasarinya: "semua master/konfigurasi yang masih bersama
harus jadi per entitas". Contoh nyata yang memaksanya: PT Kain Suka Cita PKP dengan
karyawan tetap (BPJS penuh) vs CV Kanda Suka non-PKP dengan tenaga borongan.
"""
from config_registry import E
from core_utils import rupiah

# Global + override per badan usaha (mesin pembacanya sudah menghormati keduanya).
G = ("global", "entity")

# ═══════════════════════════════════════════════════════════════════════════
# KONVERSI SATUAN (scope `uom`)
# ═══════════════════════════════════════════════════════════════════════════
# Wewenang mengubah = IZIN di matriks peran (KF-T1, K-47), bukan nama peran. Asal-usulnya (FASE G-0):
#   PUT /uom-conversions/settings   → uom.update
#   PUT /lots/settings              → dulu require_role(["manager"]) → kini inventory.configure (admin, manager)
#   PUT /supplier-contracts/policy  → dulu require_role(["admin","manager"]) → kini makloon.configure (admin, manager)
#   mode surat jalan supplier       → goods_receipt.configure (admin, manager)
_UOM_PERM = ("uom", "update")
_LOT_PERM = ("inventory", "configure")
_GRN_PERM = ("goods_receipt", "configure")
_MAKLOON_PERM = ("makloon", "configure")

# KP-T4 — alasan baku kunci persetujuan yang pindah ke Aturan Persetujuan.
_KPT4_TIDAK_DIPAKAI = ("Dipindah ke Aturan Persetujuan (Pengaturan › Persetujuan › Aturan Persetujuan). Nilai terakhirnya hanya membentuk aturan bawaan selama aturan belum disimpan.")

E("uom.warn_pct", group="penerimaan", section="konversi-satuan", type="pct", default=2.0, min=0, max=100, step=0.5,
  unit="%", scopes=G, simulate="uom_variance",
  label="Selisih konversi — batas peringatan",
  help="Bila hasil konversi satuan berbeda dari angka yang diharapkan melebihi persen ini, sistem memberi "
       "peringatan (masih boleh lanjut). Isi 0 = setiap selisih sekecil apa pun diberi peringatan.",
  impact="Menentukan kapan petugas mendapat peringatan selisih konversi satuan.",
  example="Harapan 47,25 kg · hasil 48,5 kg (+2,6%) · batas 2% → muncul peringatan",
  consumers=("services/uom_rules_service.py",),
  related=("uom.block_pct",), risk="medium",
  permission=_UOM_PERM)

E("uom.block_pct", group="penerimaan", section="konversi-satuan", type="pct", default=5.0, min=0, max=100, step=0.5,
  unit="%", scopes=G, simulate="uom_variance",
  label="Selisih konversi — batas tolak",
  help="Selisih konversi di atas persen ini ditolak, kecuali petugas berizin melewatinya dengan alasan. Isi 0 = "
       "setiap selisih sekecil apa pun ditolak.",
  impact="Melindungi angka stok dari salah ketik besar saat memakai satuan pemasok.",
  example="Selisih 7% · batas 5% → ditolak",
  consumers=("services/uom_rules_service.py",),
  related=("uom.allow_override",), risk="high",
  permission=_UOM_PERM)

E("uom.allow_override", group="penerimaan", section="konversi-satuan", type="bool", default=True, scopes=G,
  label="Boleh lewati batas tolak dengan alasan",
  help="Bila aktif, petugas berizin boleh melewati batas tolak selisih konversi dengan menulis alasan yang tercatat.",
  impact="Bila mati, tidak ada jalan keluar saat kiriman memang berbeda — dokumen harus dikoreksi.",
  example="Aktif → selisih 7% bisa lanjut dengan alasan 'kiriman lebih, disetujui Manajer'",
  consumers=("services/uom_rules_service.py", "services/inbound_complete_service.py"), risk="high",
  permission=_UOM_PERM)

E("uom.precision", group="penerimaan", section="konversi-satuan", type="int", default=2, min=0, max=6, step=1,
  unit="desimal", scopes=G,
  label="Jumlah desimal hasil konversi",
  help="Banyak angka di belakang koma untuk hasil konversi satuan. Isi 0 = hasil dibulatkan ke angka bulat.",
  impact="Mengubah pembulatan jumlah yang tersimpan — berpengaruh pada kecocokan stok.",
  example="2 desimal → 47,2534 kg disimpan 47,25 kg",
  consumers=("services/uom_rules_service.py",), risk="medium",
  permission=_UOM_PERM)

E("uom.require_trail", group="penerimaan", section="konversi-satuan", type="bool", default=True, scopes=G,
  label="Wajib simpan jejak konversi",
  help="Menyimpan asal angka: satuan & jumlah dokumen, faktor yang dipakai, dan sumber faktor.",
  impact="Bila mati, angka stok tidak bisa dipertanggungjawabkan ke surat jalan pemasok.",
  example="Aktif → tercatat '25 cone × 1,89 = 47,25 kg (sumber: barang pemasok)'",
  consumers=("services/uom_rules_service.py",), risk="high",
  permission=_UOM_PERM)

# ═══════════════════════════════════════════════════════════════════════════
# LOT & KETERTELUSURAN (scope `lot`)
# ═══════════════════════════════════════════════════════════════════════════
E("lot.enforcement_mode", group="penerimaan", section="nomor-lot", type="enum", default="warn",
  options=({"value": "off", "label": "Tidak diwajibkan"},
           {"value": "warn", "label": "Beri peringatan bila kosong"},
           {"value": "block", "label": "Tolak bila kosong"}),
  scopes=G, simulate="lot_enforce",
  label="Nomor lot wajib diisi saat terima barang?",
  help="Seberapa keras sistem menuntut nomor lot diisi saat barang masuk: tidak diwajibkan, diberi peringatan, atau "
       "ditolak bila kosong.",
  impact="Mode 'Tolak bila kosong' menolak penerimaan tanpa nomor lot — ketertelusuran terjamin tapi gudang bisa "
         "terhambat bila pemasok tidak mencantumkan lot.",
  example="Tolak bila kosong → penerimaan tanpa nomor lot pemasok ditolak",
  consumers=("services/lot_service.py", "services/inbound_complete_service.py"), risk="high",
  permission=_LOT_PERM)

E("lot.require_supplier_lot", group="penerimaan", section="nomor-lot", type="bool", default=True, scopes=G,
  simulate="lot_enforce",
  label="Wajib nomor lot dari pemasok",
  help="Meminta nomor lot yang tertulis di surat jalan pemasok. Seberapa keras dimintanya mengikuti pengaturan di "
       "atas.",
  impact="Menentukan field mana yang diperiksa oleh ketegasan pengisian lot di atas.",
  example="Aktif + Tolak bila kosong → isian Lot Pemasok wajib diisi",
  consumers=("services/lot_service.py",), risk="medium",
  permission=_LOT_PERM)

E("lot.require_dye_lot", group="penerimaan", section="nomor-lot", type="bool", default=True, scopes=G,
  simulate="lot_enforce",
  label="Wajib nomor celup (dye lot)",
  help="Nomor celup menentukan kesamaan warna — kunci untuk menghindari klaim beda warna.",
  impact="Menentukan apakah dye lot diperiksa saat penerimaan dan alokasi warna.",
  example="Aktif → roll tanpa dye lot diberi peringatan/ditolak sesuai mode",
  consumers=("services/lot_service.py",),
  related=("allocation.dye_lot_strict",), risk="medium",
  permission=_LOT_PERM)

E("lot.alias_mode", group="penerimaan", section="nomor-lot", type="enum", default="manual",
  options=({"value": "manual", "label": "Diisi petugas per lot"},
           {"value": "off", "label": "Mati (sama dengan Diisi petugas per lot)"}),
  scopes=G,
  label="Nama lot versi kita (alias)",
  help="Selain nomor lot pabrik, petugas boleh memberi nama lot versi kita (mis. lot pemasok 234 disebut “KN A”). "
       "Nomor lot asli tidak berubah.",
  impact="Mode manual mengizinkan petugas mengisi alias per lot dengan jejak riwayat; nomor lot internal tetap tidak berubah.",
  example="Diisi petugas per lot → lot KSC/LOT-2610-0001 (pemasok 234) boleh diberi nama 'KN A'",
  consumers=("services/lot_service.py",), risk="medium", permission=_LOT_PERM)

E("lot.alias_unique_scope", group="penerimaan", section="nomor-lot", type="enum", default="entity_supplier",
  options=({"value": "entity_supplier", "label": "Unik per PT + pemasok"},
           {"value": "entity", "label": "Unik per PT (lintas pemasok)"}),
  scopes=G,
  label="Nama lot versi kita tak boleh kembar di",
  help="Menentukan apakah nama lot versi kita harus unik per pemasok dalam satu PT, atau unik untuk seluruh PT.",
  impact="Mencegah dua lot berbeda punya alias sama sehingga penelusuran tidak ambigu.",
  example="Per PT + pemasok → nama 'KN A' boleh dipakai lagi untuk pemasok lain",
  consumers=("services/lot_service.py",), risk="low", permission=_LOT_PERM)

E("lot.auto_create_on_receiving", group="penerimaan", section="nomor-lot", type="bool", default=True, scopes=G,
  label="Buat lot otomatis saat penerimaan",
  help="Sistem membuat kartu lot baru otomatis ketika barang diterima, tanpa input manual.",
  impact="Bila mati, petugas harus membuat lot manual lebih dulu — lebih lambat tetapi lebih terkontrol.",
  example="Aktif → penerimaan 20 roll langsung membentuk LOT-2607-0001",
  consumers=("services/lot_service.py",), risk="medium",
  permission=_LOT_PERM)

E("lot.status_on_receipt", group="penerimaan", section="nomor-lot", type="enum", default="karantina",
  options=({"value": "karantina", "label": "Karantina (tunggu QC)"},
           {"value": "tersedia", "label": "Langsung tersedia"}),
  scopes=G,
  label="Status lot saat baru diterima",
  help="Menentukan apakah barang yang baru diterima langsung bisa dijual atau menunggu lulus QC.",
  impact="'Langsung tersedia' mempercepat penjualan tetapi melewati kendali mutu.",
  example="Karantina → stok belum bisa dijual sampai QC selesai",
  consumers=("services/lot_service.py", "services/inbound_complete_service.py"),
  related=("purchasing.qc_on_receipt",), risk="high",
  permission=_LOT_PERM)

# KF-T2 (KP-13, L5) — `lot_service.next_lot_number` tidak membaca kunci ini (nomor selalu `{KODE}/LOT-YYMM-####`);
# pembacanya hanya simulator. Ditandai tidak dipakai sampai format bisa diatur (unit KP-T5).
# KP-T5 — format nomor lot kini diatur di tabel Penomoran Dokumen (jenis `lot`, `doc_number_kinds.py`); kunci ini tetap
# tidak dipakai.
E("lot.number_format", group="penerimaan", section="nomor-lot", type="text", default="LOT-YYMM-####", scopes=G,
  label="Format nomor lot",
  help="Pola nomor lot otomatis. YY = tahun 2 digit, MM = bulan, #### = urutan.",
  impact="Mengubah bentuk nomor lot baru. Nomor lama tidak berubah.",
  example="'KN-LOT-YYMM-#####' → KN-LOT-2607-00001",
  consumers=("services/lot_service.py",), risk="low",
  permission=_LOT_PERM, status="not_used",
  not_used_reason="Nomor lot saat ini selalu berbentuk KODE-PT/LOT-TTBB-urutan. Format yang bisa diatur menyusul "
                  "bersama penomoran dokumen. Diatur di Pengaturan › Dokumen & Notifikasi › Penomoran Dokumen.")

# ═══════════════════════════════════════════════════════════════════════════
# PENERIMAAN BARANG (scope `receiving`)
# ═══════════════════════════════════════════════════════════════════════════
E("receiving.supplier_uom_input_mode", group="penerimaan", section="menerima", type="enum", default="prefer",
  options=({"value": "off", "label": "Nonaktif — hanya satuan KN"},
           {"value": "optional", "label": "Opsional — petugas boleh memilih"},
           {"value": "prefer", "label": "Diutamakan — satuan pemasok terpilih otomatis"}),
  scopes=G,
  label="Ketik jumlah pakai satuan pemasok",
  help="Petugas boleh mengetik jumlah seperti tertulis di surat jalan pemasok (mis. 25 cone) dan sistem mengubahnya "
       "ke satuan kita (kg).",
  impact="Mengurangi salah hitung manual. Mode 'Nonaktif' memaksa petugas mengonversi sendiri.",
  example="Diutamakan → satuan 'cone' langsung terpilih, ketik 25 → tersimpan 47,25 kg",
  consumers=("services/receiving_uom_service.py:uom_options",), risk="medium")

E("receiving.require_supplier_item_for_supplier_uom", group="penerimaan", section="menerima", type="bool",
  default=True, scopes=G,
  label="Satuan pemasok wajib terdaftar",
  help="Satuan pemasok hanya boleh dipakai bila angka konversinya sudah diisi di data Barang Pemasok, bukan "
       "perkiraan umum.",
  impact="Bila mati, sistem boleh memakai faktor konversi umum — lebih longgar tetapi "
       "berisiko salah untuk barang tertentu.",
  example="Aktif → satuan 'cone' tanpa data barang pemasok ditolak dengan petunjuk perbaikan",
  consumers=("services/receiving_uom_service.py:uom_options",), risk="medium")

E("receiving.supplier_dn_mode", group="penerimaan", section="menerima", type="enum", default="warn",
  options=({"value": "off", "label": "Tidak diperiksa"},
           {"value": "warn", "label": "Ingatkan bila kosong (tetap boleh simpan)"},
           {"value": "block", "label": "Wajib diisi"}),
  scopes=G,
  label="Nomor surat jalan pemasok wajib diisi?",
  help="Menentukan apakah penerimaan barang tanpa nomor surat jalan pemasok dibiarkan, diberi peringatan, atau "
       "ditolak.",
  impact="'Ingatkan bila kosong' → penerimaan tanpa surat jalan tetap tersimpan dengan peringatan & tanda 'surat "
         "jalan belum diisi'; 'Wajib diisi' → ditolak.",
  example="Wajib diisi → Selesaikan Penerimaan tanpa nomor surat jalan ditolak",
  consumers=("services/inbound_complete_service.py",), risk="medium", permission=_GRN_PERM)

E("receiving.block_over_remaining", group="penerimaan", section="menerima", type="bool", default=True,
  scopes=G, simulate="receiving_over",
  label="Tolak penerimaan melebihi sisa PO",
  help="Bila aktif, penerimaan yang melewati sisa PO + toleransi DITOLAK. Bila mati, "
       "penerimaan tetap diterima namun ditandai 'lebih dari PO' untuk ditinjau.",
  impact="Aktif = disiplin PO terjaga (butuh Eskalasi bila kiriman memang lebih). "
         "Mati = gudang tidak terhambat, tetapi selisih harus ditindaklanjuti.",
  example="Mati · PO sisa 20 kg · datang 25 kg → diterima + ditandai lebih 5 kg",
  consumers=("services/receiving_uom_service.py:preflight_scan",),
  related=("purchasing.receive_tolerance_percent",), risk="high")

E("receiving.line_qty_tolerance_pct", group="penerimaan", section="menerima", type="pct", default=2.0,
  min=0, max=50, step=0.5, unit="%", scopes=G,
  label="Toleransi total roll vs jumlah diterima",
  help="Saat menyelesaikan penerimaan, jumlah panjang/berat semua roll boleh berbeda dari jumlah yang diterima "
       "sebesar persen ini (minimal 0,5 satuan). Isi 0 = hanya selisih 0,5 satuan yang dimaafkan.",
  impact="Makin kecil, petugas harus makin teliti mengukur roll; makin besar, selisih kecil lolos tanpa ditanya.",
  example="Diterima 1.000 m · toleransi 2% → total roll 980–1.020 m masih diterima",
  consumers=("services/inbound_complete_service.py:complete_task",
             "services/receiving_uom_service.py:uom_options"),
  related=("receiving.label_variance_tolerance_percent",), risk="medium")

E("receiving.mode", group="penerimaan", section="menerima", type="enum", default="legacy",
  options=({"value": "legacy", "label": "Cara lama (per tugas Barang Masuk)"},
           {"value": "grn", "label": "Per kedatangan (surat jalan)"}),
  scopes=G,
  label="Cara mencatat barang datang",
  help="Per kedatangan: tiap surat jalan dicatat, dihitung fisik, lalu dicocokkan sebelum stok masuk. Cara lama: "
       "barang diterima langsung per tugas Barang Masuk.",
  impact="Mode 'Per kedatangan' menolak scan/terima/selesai lewat layar lama untuk tugas baru; tugas yang sudah "
         "setengah jalan tetap boleh diselesaikan di layar lama.",
  example="Per kedatangan → petugas mencatat tiap surat jalan, menghitung fisik, lalu mencocokkannya",
  consumers=("services/goods_receipt_service.py:guard_legacy_receiving",), risk="high",
  edit_at={"view": "settings-receiving-ocr", "preset": {"tab": "mode"}, "label": "Penerimaan Barang › Mode Penerimaan"})

E("receiving.blind_count", group="penerimaan", section="menerima", type="bool", default=True, scopes=G,
  label="Hitung tanpa melihat angka surat jalan",
  help="Petugas hitung tidak diperlihatkan jumlah, roll, dan berat yang tertulis di surat jalan, supaya hitungan "
       "fisik tidak sekadar menyalin angka pemasok.",
  impact="Aktif = hitungan fisik independen dari klaim pemasok. Mati = penghitung bisa menyalin angka SJ.",
  example="Aktif → layar Hitung hanya menampilkan barang & target, tanpa '21 pcs · 2.186 yd'",
  consumers=("services/goods_receipt_service.py:is_blind_for",), risk="medium")

# ── GRN Fase 4 — OCR surat jalan (§4.9) ──────────────────────────────────────
_OCR_C = ("services/goods_receipt_ocr_service.py:ocr_config",)
E("receiving.min_photo_short_side_px", group="sistem", section="baca-sj", type="int", default=1000, scopes=("global",),
  label="Ukuran minimum foto surat jalan", help="Foto yang sisi pendeknya kurang dari sekian piksel diberi "
                                                "peringatan, karena foto kecil (mis. kiriman WhatsApp) sering salah "
                                                "terbaca. Isi 0 = ukuran foto tidak diperiksa.",
  impact="Terlalu kecil → OCR sering salah baca angka.", example="1000 → foto 800×1200 diberi peringatan, diminta "
                                                                 "foto ulang", consumers=_OCR_C, risk="low",
  unit="piksel")
E("receiving.client_po_patterns", group="sistem", section="baca-sj", type="list",
  default=[r"(?P<core>\d{3,5})/(CST|SCB)/\d{4}", r"[A-Z]+/PO-(?P<core>\d+)"], scopes=G,
  label="Pola nomor PO kita di surat jalan",
  help="Dipakai sistem untuk mengenali nomor PO kita di surat jalan pemasok. Pengaturan teknis; diisi tim teknis.",
  impact="Pola salah → baris SJ tidak menemukan PO-nya (harus dipilih manual).", example="(?P<core>\\d{3,5})/CST/\\d{4}",
  consumers=_OCR_C, risk="medium", value_format="regex")
E("receiving.ocr_enabled", group="sistem", section="baca-sj", type="bool", default=False, scopes=G,
  label="Baca surat jalan otomatis dengan AI", help="Foto surat jalan dikirim ke layanan AI (OpenAI) untuk dibaca "
                                                    "otomatis. Bila mati, isi surat jalan diketik manual.",
  impact="Data surat jalan dikirim ke pihak luar; aktifkan hanya bila perusahaan sudah menyetujuinya.", example="Aktif "
                                                                                                                "untuk "
                                                                                                                "PT "
                                                                                                                "yang "
                                                                                                                "sudah "
                                                                                                                "setuju", consumers=_OCR_C, risk="high")
E("receiving.ocr_model_primary", group="sistem", section="baca-sj", type="text", default="gpt-6-sol", scopes=("global",),
  label="Model AI pembaca surat jalan", help="Nama model AI yang membaca foto surat jalan. Bila model tidak "
                                             "tersedia, pembacaan gagal dan surat jalan diisi manual. Pengaturan "
                                             "teknis.",
  impact="Model tak tersedia → pembacaan gagal (OCR_API) dan GRN kembali ke isi manual.", example="gpt-6-sol",
  consumers=_OCR_C, risk="medium")
E("receiving.ocr_model_second", group="sistem", section="baca-sj", type="text", default="gpt-5.6-sol", scopes=("global",),
  label="Model AI pemeriksa kedua", help="Model AI kedua yang dipanggil untuk membandingkan hasil saat bacaan "
                                         "pertama meragukan. Perbedaannya disorot di layar tinjau.",
  impact="Beda hasil disorot di layar tinjau; tidak ada pemungutan suara otomatis.", example="gpt-5.6-sol",
  consumers=_OCR_C, risk="low")
E("receiving.ocr_auto_orient", group="sistem", section="baca-sj", type="bool", default=True, scopes=("global",),
  label="Putar foto surat jalan otomatis", help="Sebelum dibaca, model kecil menebak apakah foto miring 90°/180° lalu memutarnya tegak.",
  impact="Mati → foto miring dibaca apa adanya (nomor PO & nama sering salah baca).", example="Aktif",
  consumers=_OCR_C, risk="low")
E("receiving.ocr_photo_check", group="sistem", section="baca-sj", type="bool", default=True, scopes=("global",),
  label="Cek mutu foto surat jalan setelah dipotret", help="Sesaat setelah foto diambil, AI menilai apakah terpotong, buram, silau, atau sulit dibaca — staf diminta foto ulang sebelum dikirim.",
  impact="Mati → hanya cek cepat di HP (resolusi, buram, gelap, silau); foto terpotong tidak terdeteksi.", example="Aktif",
  consumers=_OCR_C, risk="low")
E("receiving.ocr_orient_model", group="sistem", section="baca-sj", type="text", default="gpt-6-sol", scopes=("global",),
  label="Model AI pemutar foto", help="Model AI kecil yang menebak apakah foto miring lalu memutarnya tegak sebelum "
                                      "dibaca. Pengaturan teknis.",
  impact="Model tak tersedia → foto dikirim tanpa diputar.", example="gpt-6-sol", consumers=_OCR_C, risk="low")
E("receiving.ocr_second_reader_mode", group="sistem", section="baca-sj", type="enum", default="on_doubt", scopes=("global",),
  options=({"value": "off", "label": "Mati"}, {"value": "on_doubt", "label": "Saat ragu"}, {"value": "always", "label": "Selalu"}),
  label="Kapan dibaca ulang model kedua", help="Tidak pernah, hanya saat bacaan pertama meragukan, atau selalu. "
                                               "“Selalu” membuat biaya sekitar dua kali lipat.",
  impact="Selalu = biaya ±2×.", example="Hanya bila meragukan → surat jalan yang bacaannya ragu dibaca ulang, "
                                        "sisanya cukup sekali", consumers=_OCR_C, risk="low")
E("receiving.ocr_reasoning_effort", group="sistem", section="baca-sj", type="enum", default="low", scopes=("global",),
  options=({"value": "none", "label": "Tanpa"}, {"value": "low", "label": "Rendah"}, {"value": "medium", "label": "Sedang"}),
  label="Ketelitian AI membaca surat jalan", help="Makin tinggi makin teliti, tetapi lebih lambat dan lebih mahal.", impact="Lebih tinggi = lebih lambat & mahal.",
  example="Rendah → cukup untuk surat jalan cetak yang jelas", consumers=_OCR_C, risk="low")
E("receiving.ocr_max_output_tokens", group="sistem", section="baca-sj", type="int", default=6000, scopes=("global",),
  label="Batas panjang hasil baca AI", help="Batas panjang jawaban AI per surat jalan. Bila terlalu kecil, surat "
                                            "jalan yang panjang terpotong dan harus diisi manual. Pengaturan "
                                            "teknis. Isi lebih dari 0; 0 membuat pembacaan gagal dan surat jalan "
                                            "diisi manual.", impact="Biaya maksimum per panggilan.",
  example="6000", consumers=_OCR_C, risk="low",
  unit="token")
E("receiving.ocr_image_max_side", group="sistem", section="baca-sj", type="int", default=2048, scopes=("global",),
  label="Ukuran foto yang dikirim ke AI", help="Foto diperkecil sampai sisi panjangnya sekian piksel sebelum "
                                               "dikirim. Lebih besar lebih jelas, tetapi lebih mahal. Isi lebih "
                                               "dari 0; 0 membuat pembacaan gagal dan surat jalan diisi manual.", impact="Lebih besar = lebih mahal.",
  example="2048", consumers=_OCR_C, risk="low",
  unit="piksel")
E("receiving.ocr_max_pages", group="sistem", section="baca-sj", type="int", default=5, min=1, max=50, scopes=("global",),
  label="Halaman maksimum per surat jalan", help="Surat jalan dengan halaman lebih dari angka ini tidak dibaca AI "
                                                 "dan harus diisi manual, untuk membatasi biaya.", impact="Batas biaya.",
  example="5", consumers=_OCR_C, risk="low",
  unit="halaman")
E("receiving.ocr_extract_packing_list", group="sistem", section="baca-sj", type="bool", default=True, scopes=G,
  label="Baca juga rincian roll (packing list)", help="Bila aktif, AI juga membaca daftar roll di packing list, "
                                                      "bukan hanya ringkasan surat jalan. Biayanya sedikit lebih "
                                                      "besar.",
  impact="Token keluaran lebih banyak.", example="Aktif → daftar 12 roll di packing list ikut terisi", consumers=_OCR_C, risk="low")
E("receiving.ocr_monthly_budget_usd", group="sistem", section="baca-sj", type="decimal", default=75, scopes=("global",),
  label="Anggaran baca surat jalan per bulan (USD)", help="Bila biaya bulan berjalan mencapai angka ini, AI "
                                                          "berhenti dipakai dan surat jalan diisi manual sampai "
                                                          "bulan berikutnya. Isi 0 = tanpa batas anggaran.",
  impact="Rem biaya.", example="75", consumers=_OCR_C, risk="medium",
  unit="USD")
E("receiving.ocr_budget_warn_pct", group="sistem", section="baca-sj", type="pct", default=80, scopes=("global",),
  label="Peringatan anggaran AI terpakai (%)", help="Admin diberi tahu sekali sebulan saat pemakaian mencapai "
                                                    "persen ini dari anggaran. Isi 0 = tidak ada pemberitahuan.", impact="Hanya "
                                                                                                                         "mengatur "
                                                                                                                         "kapan "
                                                                                                                         "peringatan "
                                                                                                                         "dikirim; "
                                                                                                                         "tidak "
                                                                                                                         "menghentikan "
                                                                                                                         "AI.",
  example="80", consumers=_OCR_C, risk="low",
  unit="%")
E("receiving.ocr_price_table", group="sistem", section="baca-sj", type="text",
  default='{"gpt-6-sol": {"in": 2.0, "cached_in": 0.2, "out": 10.0}, "gpt-6-luna": {"in": 0.5, "cached_in": 0.05, "out": 2.0}, "gpt-5.6-sol": {"in": 5.0, "cached_in": 0.5, "out": 30.0}, "price_version": "2026-09-28"}',
  scopes=("global",), label="Tabel harga layanan AI (teknis)",
  help="Daftar harga per model untuk menghitung biaya. Diisi tim teknis saat harga penyedia berubah.", impact="Laporan biaya & rem anggaran.",
  example="Satu baris per model: harga masukan, masukan tersimpan, dan keluaran per sejuta token", consumers=_OCR_C, risk="low",
  value_format="json_map")

E("receiving.label_variance_tolerance_percent", group="penerimaan", section="menerima", type="pct", default=2.0,
  min=0, max=50, step=0.5, unit="%", scopes=G,
  label="Toleransi selisih label pemasok vs aktual",
  help="Saat roll hasil scan label ditimbang/diukur ulang, selisih di atas angka ini ditandai 'selisih label vs "
       "aktual' dan masuk antrean QC. Isi 0 = setiap selisih ditandai.",
  impact="Makin kecil, makin banyak roll masuk QC; makin besar, selisih stok baru ketahuan saat potong.",
  example="Label 100 yd · aktual 97 yd · toleransi 2% → selisih 3% → ditandai QC",
  consumers=("routers/inbound_scan_label.py:_tolerance_pct",),
  related=("purchasing.receive_tolerance_percent",), risk="medium")

E("receiving.auto_rfid_on_scan", group="penerimaan", section="menerima", type="bool", default=True, scopes=G,
  label="Buat tag RFID otomatis saat scan label",
  help="Begitu roll tercatat dari scan label pemasok, sistem langsung membuat nomor tag RFID-nya; petugas tinggal "
       "menempel tag. Bila mati, tag dibuat satu per satu.",
  impact="Aktif = identitas roll KN siap ditelusuri RFID sejak menit pertama. Mati = tagging manual.",
  example="Aktif → scan label → RL-00061 + EPC 3034… tercetak di label KN",
  consumers=("services/receiving_roll_service.py:build_receiving_roll",), risk="low")

# ═══════════════════════════════════════════════════════════════════════════
# PRODUKSI & MAKLOON (scope `makloon`)
# ═══════════════════════════════════════════════════════════════════════════
E("makloon.variance_tolerance_pct", group="pembelian", section="makloon", type="pct", default=3.0,
  min=0, max=100, step=0.5, unit="%", scopes=G, simulate="makloon_variance",
  label="Toleransi selisih hasil makloon",
  help="Selisih hasil kembali dari mitra makloon dibanding estimasi yang masih dianggap wajar. Isi 0 = setiap "
       "selisih dianggap tidak wajar.",
  impact="Selisih di atas toleransi otomatis membuka Klaim Selisih ke mitra.",
  example="Estimasi 1.000 yard · kembali 960 (−4%) · toleransi 3% → klaim terbuka",
  consumers=("services/makloon_order_service.py", "services/contract_service.py"),
  related=("makloon.auto_claim",), risk="high",
  permission=_MAKLOON_PERM)

E("makloon.auto_claim", group="pembelian", section="makloon", type="bool", default=True, scopes=G,
  label="Buka klaim otomatis saat selisih besar",
  help="Sistem langsung membuat dokumen klaim ketika selisih melewati toleransi.",
  impact="Bila mati, selisih hanya dicatat — tim harus membuat klaim manual (berisiko terlupa).",
  example="Aktif → selisih −4% otomatis membentuk klaim status 'menunggu persetujuan'",
  consumers=("services/makloon_order_service.py", "services/contract_service.py"), risk="medium",
  permission=_MAKLOON_PERM)

E("makloon.claim_approval_roles", group="pembelian", section="makloon", type="list",
  default=["manager", "admin"], scopes=G,
  label="Peran yang boleh menyetujui klaim makloon",
  help="Peran yang berwenang menyetujui tindakan klaim ke mitra makloon (potong tagihan, ganti rugi, atau diterima).",
  impact="Menentukan siapa yang bisa menutup klaim dan membebankan biaya ke mitra.",
  example="['Manajer','admin'] → supervisor gudang tidak bisa menyetujui klaim",
  consumers=("services/approval_policy_service.py:default_rows_for",), risk="high",
  permission=_MAKLOON_PERM,
  # KP-T4 — isi kunci ini pindah ke tabel kebijakan persetujuan (`approval_policies`).
  status="not_used", not_used_reason=_KPT4_TIDAK_DIPAKAI,
  items="roles")

E("makloon.contract_mode", group="pembelian", section="makloon", type="enum", default="warn",
  options=({"value": "off", "label": "Tidak diwajibkan"},
           {"value": "warn", "label": "Peringatan bila tanpa kontrak"},
           {"value": "block", "label": "Tolak bila tanpa kontrak"}),
  scopes=G,
  label="Order makloon wajib punya kontrak?",
  help="Seberapa keras order makloon harus merujuk kontrak tarif yang berlaku: tidak diwajibkan, diberi peringatan, "
       "atau ditolak bila tanpa kontrak.",
  impact="Mode 'Tolak bila tanpa kontrak' mencegah order tanpa kontrak — tarif selalu terkendali, tetapi mitra baru "
         "harus dibuatkan kontrak lebih dulu.",
  example="Tolak bila tanpa kontrak → order makloon tanpa kontrak aktif ditolak",
  consumers=("services/makloon_order_service.py", "services/contract_service.py"), risk="high",
  permission=_MAKLOON_PERM)

E("makloon.default_shrinkage_pct", group="pembelian", section="makloon", type="pct", default=0.0,
  min=0, max=100, step=0.5, unit="%", scopes=G, simulate="makloon_variance",
  label="Susut standar proses makloon",
  help="Perkiraan penyusutan bawaan proses (mis. penyusutan kain saat dicelup) bila kontrak belum mencantumkan "
       "angkanya. Isi 0 = tidak ada penyusutan yang diperkirakan.",
  impact="Mempengaruhi estimasi hasil dan perhitungan selisih/klaim.",
  example="Susut 3% · kirim 1.000 yard → estimasi kembali 970 yard",
  consumers=("services/makloon_order_service.py", "services/contract_service.py"), risk="medium",
  permission=_MAKLOON_PERM)

E("makloon.require_output_product", group="pembelian", section="makloon", type="bool", default=True, scopes=G,
  label="Wajib tentukan produk hasil",
  help="Order makloon harus menyebutkan produk hasil, bukan hanya produk bahan.",
  impact="Bila mati, hasil makloon bisa masuk tanpa identitas produk — HPP & stok jadi kabur.",
  example="Aktif → langkah celup wajib memilih produk hasil 'Lurik Merah Grade A'",
  consumers=("services/makloon_order_service.py", "services/contract_service.py"), risk="medium",
  permission=_MAKLOON_PERM)

E("makloon.require_yield_reason", group="pembelian", section="makloon", type="bool", default=True, scopes=G,
  label="Wajib alasan bila estimasi hasil diubah",
  help="Bila petugas menimpa angka estimasi hasil, alasannya wajib ditulis dan masuk audit.",
  impact="Menjaga agar estimasi tidak diubah diam-diam untuk menutupi selisih.",
  example="Aktif → mengubah estimasi 970 → 940 wajib mengisi alasan",
  consumers=("routers/makloon_orders.py", "services/contract_service.py"), risk="medium",
  permission=_MAKLOON_PERM)

# ═══════════════════════════════════════════════════════════════════════════
# SDM & PENGGAJIAN (scope `hr`)
# ═══════════════════════════════════════════════════════════════════════════
# FASE G-0 — editor lama `PayrollSetupView` DIHAPUS dan digabung ke Pusat
# Pengaturan. Agar penggabungan itu tidak diam-diam MENCABUT wewenang manager
# (yang sejak dulu boleh menulis PUT /api/hr/payroll/settings lewat izin
# `hr.manage_payroll`), setting yang dulu tercakup `SETTINGS_KEYS` di
# routers/hr_payroll.py memakai izin domainnya sendiri, bukan `settings.manage`.
_HR_PAYROLL = ("hr", "manage_payroll")

_BPJS = (
    ("kes_rate_employee", 1.0, "BPJS Kesehatan — potongan karyawan",
     "Persen gaji yang dipotong dari karyawan untuk BPJS Kesehatan."),
    ("kes_rate_employer", 4.0, "BPJS Kesehatan — beban perusahaan",
     "Persen gaji yang dibayar perusahaan untuk BPJS Kesehatan."),
    ("jht_rate_employee", 2.0, "JHT — potongan karyawan",
     "Persen gaji yang dipotong dari karyawan untuk Jaminan Hari Tua."),
    ("jht_rate_employer", 3.7, "JHT — beban perusahaan",
     "Persen gaji yang dibayar perusahaan untuk Jaminan Hari Tua."),
    ("jp_rate_employee", 1.0, "Jaminan Pensiun — potongan karyawan",
     "Persen gaji yang dipotong dari karyawan untuk Jaminan Pensiun."),
    ("jp_rate_employer", 2.0, "Jaminan Pensiun — beban perusahaan",
     "Persen gaji yang dibayar perusahaan untuk Jaminan Pensiun."),
    ("jkm_rate_employer", 0.3, "JKM — beban perusahaan",
     "Persen gaji yang dibayar perusahaan untuk Jaminan Kematian."),
)
for _f, _d, _lab, _help in _BPJS:
    E(f"hr.bpjs.{_f}", group="sdm", section="bpjs", type="pct", default=_d, min=0, max=100, step=0.1,
      unit="%", scopes=G, simulate="payroll_bpjs",
      # KF-T4 — arti 0 (tarif × upah = 0) dan istilah glosarium ("penggajian", tanpa "diposting").
      label=_lab, help=_help + (" Isi 0 = tidak ada potongan ini." if _f.endswith("_employee")
                                else " Isi 0 = tidak ada iuran ini."),
      impact="Mengubah potongan/iuran pada slip gaji periode berikutnya. "
             "Slip gaji yang sudah disahkan tidak berubah.",
      example=f"Gaji Rp 5.000.000 · tarif {_d}% → {rupiah(int(5_000_000 * _d / 100))}",
      consumers=("services/hr_payroll_service.py", "services/hr_service.py"), risk="high",
      permission=_HR_PAYROLL)

E("hr.bpjs.kes_ceiling", group="sdm", section="bpjs", type="money", default=12000000, min=0,
  max=1000000000, step=100000, unit="Rp", scopes=G, simulate="payroll_bpjs",
  label="Batas atas upah BPJS Kesehatan",
  help="Upah di atas angka ini tidak menambah iuran BPJS Kesehatan. Isi 0 = tanpa batas atas.",
  impact="Membatasi iuran BPJS Kesehatan untuk karyawan bergaji tinggi.",
  example="Batas Rp 12.000.000 · gaji Rp 20.000.000 → iuran dihitung dari Rp 12.000.000",
  consumers=("services/hr_payroll_service.py", "services/hr_service.py"), risk="high",
  permission=_HR_PAYROLL)

E("hr.bpjs.jp_ceiling", group="sdm", section="bpjs", type="money", default=10042300, min=0,
  max=1000000000, step=100000, unit="Rp", scopes=G, simulate="payroll_bpjs",
  label="Batas atas upah Jaminan Pensiun",
  help="Upah di atas angka ini tidak menambah iuran Jaminan Pensiun (batas resmi BPJS). Isi 0 = tanpa batas atas.",
  impact="Membatasi iuran Jaminan Pensiun untuk karyawan bergaji tinggi.",
  example="Batas Rp 10.042.300 · gaji Rp 15.000.000 → iuran dari Rp 10.042.300",
  consumers=("services/hr_payroll_service.py", "services/hr_service.py"), risk="high",
  permission=_HR_PAYROLL)

E("hr.jkk_classes", group="sdm", section="bpjs", type="table",
  default=[{"class": "I", "rate": 0.24}, {"class": "II", "rate": 0.54},
           {"class": "III", "rate": 0.89}, {"class": "IV", "rate": 1.27},
           {"class": "V", "rate": 1.74}],
  scopes=G,
  row_shape="list",
  columns=({"name": "class", "label": "Kelas risiko", "type": "text", "default": "VI",
            "width": "140px"},
           {"name": "rate", "label": "Tarif JKK", "type": "pct", "default": 0.0,
            "unit": "%", "width": "140px"}),
  label="Kelas risiko JKK & tarifnya",
  help="Tarif Jaminan Kecelakaan Kerja per kelas risiko pekerjaan. Setiap karyawan "
       "dipetakan ke salah satu kelas.",
  impact="Mengubah beban JKK perusahaan pada slip gaji periode berikutnya.",
  example="Kelas III 0,89% · gaji Rp 5.000.000 → JKK Rp 44.500",
  consumers=("routers/hr.py", "routers/hr_payroll.py"), risk="high",
  permission=_HR_PAYROLL)

E("hr.ter_enabled", group="sdm", section="pph21", type="bool", default=True, scopes=G,
  simulate="payroll_pph21",
  label="Pakai metode TER untuk PPh 21",
  help="TER (Tarif Efektif Rata-rata) adalah metode resmi sejak 2024: pajak bulanan dihitung "
       "dari tarif efektif berdasarkan kategori PTKP, bukan dari perhitungan tahunan.",
  impact="Menentukan cara PPh 21 bulanan dihitung pada slip gaji.",
  example="Aktif · kategori A · bruto Rp 8.000.000 → PPh 21 memakai tarif TER kategori A",
  consumers=("services/hr_payroll_service.py",),
  related=("hr.ptkp_table",), risk="high", permission=_HR_PAYROLL)

# ── PK-46 — tabel PPh 21 dari pengaturan BERTANGGAL BERLAKU (PY-03, KP-36) ─────────────────────────────────────────────
# Bawaan = isi konstanta kode lama APA ADANYA, dipindah tanpa diketik ulang ke `data/pph21_bawaan.py` (satu-satunya
# pemakainya blok ini). Isi itu BELUM diverifikasi terhadap lampiran peraturan; tabel terverifikasi pemilik dimuat
# lewat `scripts/muat_pph21_terverifikasi.py` (K-42, titik henti H4). Bentuk nilai: tarif dalam PERSEN, batas atas
# rupiah, baris terakhir tanpa batas (`None`) — konversi dari bentuk kode lama (pecahan, `INF`) ada di `_jenjang`.
from data.pph21_bawaan import (  # noqa: E402
    BIAYA_JABATAN_MONTHLY_CAP, BIAYA_JABATAN_RATE, PASAL17, PTKP_AMOUNT, PTKP_TO_TER, TER_TABLES,
)


def _jenjang(tabel):
    """[(batas_atas, tarif pecahan)] kode lama → [{batas_atas, tarif_pct}] pengaturan (INF → tanpa batas)."""
    return [{"batas_atas": None if batas == float("inf") else batas, "tarif_pct": round(tarif * 100, 10)}
            for batas, tarif in tabel]


_KATEGORI_TER = ({"value": "A", "label": "A"}, {"value": "B", "label": "B"}, {"value": "C", "label": "C"})
_PPH21 = dict(
    group="sdm", section="pph21", scopes=("global",), bertanggal=True, risk="high", requires_reason=True, permission=_HR_PAYROLL,
    consumers=("services/hr_payroll_service.py:aturan_pph21",),
    impact="Mengubah PPh 21 yang dipotong mulai tanggal berlaku; slip periode sebelum tanggal itu tidak berubah.",
)
# `example` tanpa angka sampai berkas terverifikasi pemilik dimuat (unit PK-46 bagian Pengaturan).
_CONTOH_BERTANGGAL = ("Isi tabel tahun depan, pilih 'Berlaku sejak' awal tahun itu — slip bulan-bulan sebelumnya "
                      "tetap dihitung dengan tabel lama")

E("hr.pph21.ter_table", type="table", **_PPH21,
  default=[{"kategori": k, **baris} for k in ("A", "B", "C") for baris in _jenjang(TER_TABLES[k])],
  row_shape="list", value_format="tarif_berjenjang",
  columns=({"name": "kategori", "label": "Kategori", "type": "enum", "default": "A",
            "options": _KATEGORI_TER, "width": "110px"},
           {"name": "batas_atas", "label": "Batas atas bruto sebulan (kosong = tanpa batas)", "type": "money",
            "default": ""},
           {"name": "tarif_pct", "label": "Tarif", "type": "pct", "default": 0.0, "unit": "%", "width": "120px"}),
  label="Tarif efektif PPh 21 bulanan",
  help="Tarif menurut penghasilan bruto sebulan untuk tiap kategori. Baris terakhir tiap kategori tanpa batas atas. "
       "Bawaan sistem belum diverifikasi terhadap lampiran peraturan.",
  example=_CONTOH_BERTANGGAL)

E("hr.pph21.ptkp_to_ter", type="table", **_PPH21,
  default=dict(PTKP_TO_TER),
  row_shape="map",
  columns=({"name": "__key", "label": "Status PTKP", "type": "text", "width": "160px"},
           {"name": "__value", "label": "Kategori tarif", "type": "enum", "options": _KATEGORI_TER}),
  label="Kategori tarif per status PTKP",
  help="Status PTKP karyawan menentukan kategori A, B, atau C.",
  example="Status karyawan dicari di tabel ini; kategorinya menentukan tabel tarif efektif yang dipakai slip")

E("hr.ptkp_table", type="table", **_PPH21,
  default=dict(PTKP_AMOUNT),
  row_shape="map",
  columns=({"name": "__key", "label": "Status PTKP", "type": "text", "width": "160px"},
           {"name": "__value", "label": "PTKP setahun", "type": "money"}),
  label="PTKP setahun per status",
  help="Dipakai saat menghitung ulang pajak pada masa pajak terakhir (Desember atau bulan karyawan keluar).",
  example=_CONTOH_BERTANGGAL,
  related=("hr.ter_enabled",))

E("hr.pph21.pasal17_table", type="table", **_PPH21,
  default=_jenjang(PASAL17),
  row_shape="list", value_format="tarif_berjenjang",
  columns=({"name": "batas_atas", "label": "Batas atas penghasilan kena pajak setahun (kosong = tanpa batas)",
            "type": "money", "default": ""},
           {"name": "tarif_pct", "label": "Tarif", "type": "pct", "default": 0.0, "unit": "%", "width": "120px"}),
  label="Tarif pajak penghasilan setahun (berlapis)",
  help="Dipakai pada masa pajak terakhir.",
  example=_CONTOH_BERTANGGAL)

E("hr.pph21.biaya_jabatan_pct", type="pct", **_PPH21,
  default=round(BIAYA_JABATAN_RATE * 100, 10), min=0, max=100, step=0.01, unit="%",
  label="Biaya jabatan (% dari bruto)",
  help="Pengurang penghasilan pada hitung ulang setahun. 0 = tanpa biaya jabatan.",
  example="Persen ini dikalikan bruto setahun, lalu dibatasi batas bulanan × jumlah bulan bekerja")

E("hr.pph21.biaya_jabatan_maks_bulanan", type="money", **_PPH21,
  default=BIAYA_JABATAN_MONTHLY_CAP, min=0, max=100000000, step=1000, unit="Rp",
  label="Batas biaya jabatan per bulan (Rp)",
  help="0 = biaya jabatan selalu nol.",
  example="Batas ini dikalikan jumlah bulan bekerja dalam setahun pajak")
# ── akhir blok PK-46 ──────────────────────────────────────────────────────────────────────────────────────────────────

E("hr.overtime.multiplier", group="sdm", section="lembur", type="decimal", default=1.5, min=1, max=5,
  step=0.1, unit="× upah/jam", scopes=G, simulate="payroll_overtime",
  label="Pengali upah lembur",
  help="Kelipatan upah per jam untuk jam lembur.",
  impact="Langsung mengubah nominal lembur pada slip gaji periode berikutnya.",
  example="Upah/jam Rp 28.900 · pengali 1,5 · 4 jam → lembur Rp 173.400",
  consumers=("services/hr_payroll_service.py", "services/hr_attendance_service.py"),
  related=("hr.overtime.hours_divisor",), risk="medium", permission=_HR_PAYROLL)

E("hr.overtime.hours_divisor", group="sdm", section="lembur", type="int", default=173, min=1, max=400,
  step=1, unit="jam/bulan", scopes=G, simulate="payroll_overtime",
  label="Pembagi jam untuk upah per jam",
  help="Angka pembagi gaji bulanan menjadi upah per jam. Standar Kemnaker = 173.",
  impact="Mengubah dasar upah per jam sehingga seluruh nominal lembur berubah.",
  example="Gaji Rp 5.000.000 ÷ 173 → upah/jam Rp 28.902",
  consumers=("services/hr_payroll_service.py",), risk="medium", permission=_HR_PAYROLL)

_TOGGLES = (
    # KF-T4 — teks Lampiran A (label, penjelasan); contoh & dampak per sakelar di `_TOGGLE_TEKS`.
    ("bpjs_kesehatan", True, "Hitung BPJS Kesehatan di slip gaji",
     "Menampilkan dan menghitung potongan serta iuran BPJS Kesehatan di slip gaji."),
    ("bpjs_ketenagakerjaan", True, "Hitung BPJS Ketenagakerjaan di slip gaji",
     "Menampilkan dan menghitung JHT, Jaminan Pensiun, JKK, dan JKM di slip gaji."),
    ("pph21", True, "Potong PPh 21 di slip gaji",
     "Menghitung dan memotong PPh 21 pada slip gaji karyawan."),
    ("npwp_required", False, "Wajibkan NPWP karyawan",
     "Bila aktif, NPWP wajib diisi saat mendaftarkan karyawan baru."),
)
_TOGGLE_DAMPAK = "Mengubah komponen yang muncul & dihitung pada penggajian periode berikutnya."
_TOGGLE_TEKS = {   # sakelar → (contoh, dampak)
    "bpjs_kesehatan": ("Mati → BPJS Kesehatan tidak muncul dan tidak dipotong di slip gaji", _TOGGLE_DAMPAK),
    "bpjs_ketenagakerjaan": ("Mati → JHT, JP, JKK, JKM tidak muncul di slip gaji", _TOGGLE_DAMPAK),
    "pph21": ("Mati → PPh 21 tidak dipotong di slip gaji", _TOGGLE_DAMPAK),
    "npwp_required": ("Aktif → karyawan baru tanpa NPWP tidak bisa disimpan",
                      "Data karyawan baru tidak bisa disimpan tanpa NPWP. Tidak mengubah hitungan gaji."),
}
# Consumer NYATA per toggle (diverifikasi services/config_health.py).
_TOGGLE_CONSUMERS = {
    "bpjs_kesehatan": ("services/hr_payroll_service.py:bpjs_breakdown",),
    "bpjs_ketenagakerjaan": ("services/hr_payroll_service.py:bpjs_breakdown",),
    "pph21": ("services/hr_payroll_service.py:compute_payslip",),
    "npwp_required": ("routers/hr.py:create_employee",),
}
for _f, _d, _lab, _help in _TOGGLES:
    E(f"hr.feature_toggles.{_f}", group="sdm", section=("pph21" if _f in ("pph21", "npwp_required") else "bpjs"),
      type="bool", default=_d, scopes=G,
      label=_lab, help=_help, impact=_TOGGLE_TEKS[_f][1], example=_TOGGLE_TEKS[_f][0],
      consumers=_TOGGLE_CONSUMERS[_f], risk="high", permission=_HR_PAYROLL)

E("hr.employment_types", group="sdm", section="lembur", type="list",
  default=["tetap", "kontrak", "harian", "borongan"], scopes=G,
  label="Jenis hubungan kerja",
  help="Daftar status kepegawaian yang bisa dipilih saat mendaftarkan karyawan.",
  impact="Menentukan pilihan pada form karyawan dan aturan penggajian yang menempel padanya.",
  example="Menambah 'magang' → muncul sebagai pilihan status karyawan baru",
  consumers=("routers/hr.py", "services/hr_service.py"), risk="medium",
  items="text")

E("hr.payroll_commission_mode", group="sdm", section="lembur", type="enum", default="accrue_then_settle",
  options=({"value": "accrue_then_settle", "label": "Dicadangkan dulu, dibayar setelah lunas"},
           {"value": "pay_on_invoice", "label": "Dibayar saat faktur terbit"},
           {"value": "off", "label": "Komisi tidak lewat penggajian"}),
  scopes=G,
  label="Kapan komisi sales dibayar lewat gaji",
  help="Menentukan kapan komisi sales dibayarkan lewat penggajian: setelah pelanggan melunasi, saat faktur terbit, "
       "atau tidak lewat penggajian.",
  impact="Mengubah arus kas komisi dan risiko membayar komisi atas piutang yang belum tertagih.",
  example="Dibayar setelah lunas → komisi dibayar di bulan setelah pelanggan melunasi",
  consumers=("services/hr_payroll_service.py", "services/sales_force_service.py"),
  risk="high", permission=_HR_PAYROLL)

# PY-T2 (PY-09, K-38) — gaji/PT yang berubah di tengah bulan. Bawaan `mati` = perilaku sebelum unit ini (nilai akhir
# bulan, sebulan penuh). Pilihan `hari_kerja` menyusul di PY-T3 (kalender kerja).
E("hr.prorata_perubahan_gaji", group="sdm", section="lembur", type="enum", default="mati",
  options=({"value": "mati", "label": "Tidak diprorata: pakai nilai akhir bulan"},
           {"value": "hari_kalender", "label": "Prorata menurut hari kalender"}),
  scopes=G,
  label="Gaji berubah di tengah bulan",
  help="Menentukan cara menghitung gaji bulan saat gaji atau PT karyawan berubah di tengah bulan.",
  impact="Prorata membagi gaji bulan itu menurut jumlah hari tiap nilai berlaku; karyawan yang pindah PT dibayar "
         "kedua PT sesuai harinya.",
  example="Naik dari Rp 6.000.000 ke Rp 7.500.000 per 16 November → Rp 3.000.000 + Rp 3.750.000",
  consumers=("services/hr_compensation_service.py:segments", "services/hr_compensation_service.py:prorata_mode"),
  risk="high", requires_reason=True, permission=_HR_PAYROLL)

# ═══════════════════════════════════════════════════════════════════════════
# P01 (IMP-12 / IMP-20) — kelayakan jual per tahap & cakupan lokasi kerja gudang
# ═══════════════════════════════════════════════════════════════════════════
E("catalog.sales_hidden_stages", group="stok", section="memilih-stok", type="list", default=["grey", "yarn"],
  scopes=("global",),
  options=({"value": "yarn", "label": "Benang"}, {"value": "grey", "label": "Grey / Greige"},
           {"value": "pfd", "label": "PFD"}, {"value": "pfp", "label": "PFP"},
           {"value": "finished", "label": "Barang jadi"}, {"value": "remnant", "label": "Sisa potong"},
           {"value": "byproduct", "label": "Produk samping"}),
  label="Jenis bahan yang disembunyikan dari Sales",
  help="Jenis bahan (benang, kain mentah, dll.) yang tidak muncul saat Sales memilih produk. Kain mentah (greige) "
       "selalu disembunyikan dari Sales.",
  impact="Sales tidak melihat dan tidak bisa memesan barang dengan tahap di daftar ini — juga lewat API langsung.",
  example="Benang dan Grey / Greige (bawaan) → Sales melihat PFD/PFP, barang jadi, sisa potong, produk samping; "
          "greige tidak pernah",
  consumers=("services/product_exclusivity.py:refresh_hidden_stages",),
  risk="medium",
  items="options")

E("wms.location_scope_enforced", group="stok", section="kerja-gudang", type="bool", default=False, scopes=("global",),
  label="Petugas gudang hanya lihat lokasinya",
  help="Bila aktif, petugas gudang hanya melihat dan mengerjakan tugas di lokasi yang ditugaskan pada akunnya. "
       "Petakan lokasi tiap akun dulu sebelum mengaktifkan.",
  impact="Mengaktifkan tanpa memetakan akun membuat petugas gudang kehilangan antrean kerjanya. Petakan dulu, lalu aktifkan.",
  example="Petugas Soreang tidak melihat antrean Jakarta walau badan usahanya sama",
  consumers=("services/location_scope.py:enforced",),
  risk="high")


E("stock.atp_horizon_days", group="stok", section="memilih-stok", type="int", default=14, min=1, max=365, step=1,
  unit="hari", scopes=("global",),
  label="Janji stok: hitung barang datang dalam",
  help="Barang yang masih dalam perjalanan (PO terbuka, kiriman antar-PT) ikut dihitung sebagai stok yang boleh "
       "dijanjikan ke pelanggan bila perkiraan tibanya dalam sekian hari.",
  impact="Memperpanjang horizon menaikkan ATP (lebih banyak barang yang belum datang boleh dijanjikan); memperpendek "
         "membuat janji lebih hati-hati. Stok Tersedia tidak berubah.",
  example="14 (bawaan) → PO dengan ETA 20 hari lagi belum dihitung ke ATP",
  consumers=("services/atp_policy.py:horizon_days", "services/stock_figures.py:atp_pair",
             "services/stock_bucket_service.py:atp_detail"),
  risk="medium")


E("registration.finance_approval", group="stok", section="kerja-gudang", type="bool", default=True, scopes=("global", "entity"),
  label="Pendaftaran stok awal: setuju dua langkah",
  help="Bila aktif, pendaftaran stok awal disetujui dua langkah oleh orang berbeda: gudang menyetujui hitungan, "
       "lalu Finance menyetujui nilai dan pencatatan pembukuannya.",
  impact="Mematikan berarti satu persetujuan gudang langsung menghapus roll lama & memposting jurnal (perilaku lama). "
         "Saat aktif, hitungan yang sudah disetujui gudang terkunci; perubahan baris harus lewat 'Kembalikan'.",
  example="Aktif → Admin Gudang menyetujui hitungan REG-00003 → Finance meninjau nilai Rp −12 jt → menyetujui → jurnal terposting",
  consumers=("services/initial_registration_service.py:finance_step_required",
             "routers/initial_registration.py:approve_reg_session"),
  risk="high")


E("putaway.auto_draft", group="stok", section="kerja-gudang", type="bool", default=True, scopes=("global", "entity"),
  label="Siapkan perintah simpan barang otomatis",
  help="Begitu barang lulus QC (atau diterima tanpa QC), sistem menyiapkan konsep perintah penempatan ke gedung "
       "tujuan; admin gudang tinggal memeriksa dan menerbitkan.",
  impact="Mematikan berarti Putaway Order dibuat manual dari saran seperti sebelumnya. Draf tidak mengunci stok — "
         "barang transit tetap bisa dialokasikan/dijual sampai drafnya diterbitkan.",
  example="Aktif → QC lulus 12 roll di Gudang Transit → muncul draf PA ke Gudang Woven (8) dan Gudang Knitting (4)",
  consumers=("services/putaway_draft_service.py:auto_draft_enabled", "services/inbound_qc_common.py:auto_draft_after_release"),
  risk="low")


E("cutting.wait_warn_minutes", group="stok", section="potong", type="int", default=120, min=1, max=10080, step=10,
  unit="menit", scopes=("global", "entity"),
  label="Meja potong: tanda kuning setelah",
  help="Hasil potong yang belum diterima Admin Cutting lebih lama dari sekian menit diberi tanda kuning.",
  impact="Hanya mengubah warna penanda dan urutan perhatian di Meja Cutting; tidak mengubah stok atau tugas.",
  example="120 → potongan yang sudah 2 jam belum diterima tampil kuning",
  consumers=("services/cutting_service.py:wait_thresholds",), related=("cutting.wait_late_minutes",), risk="low")

E("cutting.wait_late_minutes", group="stok", section="potong", type="int", default=240, min=1, max=10080, step=10,
  unit="menit", scopes=("global", "entity"),
  label="Meja potong: tanda merah setelah",
  help="Lewat sekian menit, hasil potong yang belum diterima dianggap terlambat (merah) dan dihitung di spanduk "
       "peringatan.",
  impact="Mengubah jumlah 'terlambat' di spanduk Meja Cutting; tidak mengubah stok atau tugas.",
  example="240 → potongan yang sudah 4 jam belum diterima tampil merah",
  consumers=("services/cutting_service.py:wait_thresholds",), related=("cutting.wait_warn_minutes",), risk="low")


# FIX-3b (B2b CUT-4 / K-B2b-05, CUT-2 / K-B2b-06 / K-B3b-07) — sisa potong & susut potong, satu aturan untuk potong SO
# dan potong sample. KF-T5 — ketiganya bisa dibedakan per barang dari kartu barang (Master Produk › ubah barang).
E("cutting.remnant_threshold", group="stok", section="potong", type="decimal", default=2.0, min=0, max=1000, step=0.5,
  unit="satuan dasar", scopes=("global", "entity", "product"),
  label="Roll disebut sisa bila kurang dari",
  help="Sesudah dipotong, roll yang sisanya lebih pendek dari angka ini ditandai sebagai sisa potong. Isi 0 bila "
       "tidak ingin menandai. Bisa dibedakan per barang dari kartu barang.",
  impact="Roll sisa tampil berlabel sisa di stok & pemilih roll; grade mengikuti setelan grade sisa potong.",
  example="2 → roll 30 yard dipotong 28,5 → sisa 1,5 yard = sisa (remnant)",
  consumers=("services/roll_service.py:apply_remnant_rule",), related=("cutting.remnant_grade",), risk="low")

E("cutting.remnant_grade", group="stok", section="potong", type="enum", default="keep",
  options=({"value": "keep", "label": "Grade tetap sampai diinspeksi"},
           {"value": "BS", "label": "Jadi BS"},
           {"value": "C", "label": "Jadi C"}),
  scopes=("global", "entity", "product"),
  label="Grade roll sisa potong",
  help="Grade yang diberikan pada roll sisa. Bawaan: grade tidak diubah sampai roll diinspeksi. Bisa dibedakan per "
       "barang dari kartu barang.",
  impact="Mengubah grade roll sisa saat potong dikonfirmasi; grade asalnya tetap tercatat.",
  example="BS → sisa 1,5 yard grade A menjadi BS",
  consumers=("services/roll_service.py:apply_remnant_rule",), related=("cutting.remnant_threshold",), risk="medium")

E("cutting.waste_limit_pct", group="stok", section="potong", type="pct", default=3.0, min=0, max=100, step=0.5,
  scopes=("global", "entity", "product"),
  label="Susut potong tanpa alasan maksimal",
  help="Susut saat memotong yang melebihi persen ini dari panjang potong wajib diberi alasan. Isi 0 = setiap susut "
       "wajib diberi alasan. Bisa dibedakan per barang dari kartu barang.",
  impact="Susut di atas batas tanpa alasan ditolak; jurnal susut tetap dibuat untuk semua susut > 0.",
  example="3% → potong 20 yard dengan susut 0,8 yard (4%) wajib beralasan",
  consumers=("services/roll_service.py:confirm_cut",), risk="low",
  unit="%")


E("returns.evidence_required_submit", group="retur-koreksi", section="retur", type="bool", default=False, scopes=("global", "entity"),
  label="Retur: bukti foto wajib saat diajukan",
  help="Bila aktif, retur tidak bisa diajukan untuk persetujuan tanpa minimal satu foto atau dokumen bukti. Bila "
       "mati, bukti boleh menyusul.",
  impact="Menahan langkah 'diajukan untuk persetujuan' sampai ada minimal satu foto/dokumen di panel Lampiran bukti.",
  example="Aktif → Sales wajib mengunggah foto kain cacat sebelum retur diajukan untuk persetujuan",
  consumers=("services/return_evidence_service.py:policy",), risk="low")

E("returns.evidence_required_approve", group="retur-koreksi", section="retur", type="bool", default=False, scopes=("global", "entity"),
  label="Retur: bukti foto wajib saat disetujui",
  help="Bila aktif, retur tidak bisa disetujui tanpa minimal satu foto atau dokumen bukti.",
  impact="Menahan langkah 'disetujui' sampai ada minimal satu foto/dokumen di panel Lampiran bukti.",
  example="Aktif → Sales wajib mengunggah foto kain cacat sebelum retur disetujui",
  consumers=("services/return_evidence_service.py:policy",), risk="low")

E("returns.evidence_required_inspect", group="retur-koreksi", section="retur", type="bool", default=False, scopes=("global", "entity"),
  label="Retur: bukti foto wajib saat inspeksi",
  help="Bila aktif, inspeksi retur tidak bisa ditutup tanpa minimal satu foto atau dokumen bukti.",
  impact="Menahan langkah 'inspeksi diselesaikan' sampai ada minimal satu foto/dokumen di panel Lampiran bukti.",
  example="Aktif → petugas gudang wajib mengunggah foto kain sebelum menutup inspeksi",
  consumers=("services/return_evidence_service.py:policy",), risk="low")

E("returns.evidence_required_settle", group="retur-koreksi", section="retur", type="bool", default=False, scopes=("global", "entity"),
  label="Retur: bukti foto wajib saat diselesaikan",
  help="Bila aktif, retur tidak bisa diselesaikan (uang dikembalikan, dijadikan saldo, atau potongan harga) tanpa "
       "bukti.",
  impact="Menahan langkah 'diselesaikan (pengembalian dana/store credit/nego)' sampai ada minimal satu foto/dokumen "
         "di panel Lampiran bukti.",
  example="Aktif → Sales wajib mengunggah foto kain cacat sebelum retur diselesaikan (pengembalian dana/store "
          "credit/nego)",
  consumers=("services/return_evidence_service.py:policy",), risk="low")

E("returns.block_resend_to_origin_customer", group="retur-koreksi", section="retur", type="bool", default=True, scopes=("global", "entity"),
  label="Roll retur tak dikirim lagi ke pengembali",
  help="Roll yang pernah diretur seorang pelanggan, termasuk potongannya, tidak dialokasikan lagi ke pelanggan yang "
       "sama; tetap bisa dijual ke pelanggan lain.",
  impact="Alokasi otomatis melewati roll tersebut untuk pelanggan asal; pilihan roll manual untuk pelanggan itu "
         "ditolak.",
  example="Roll RL-10124 diretur Toko A → tidak bisa dipesan lagi untuk Toko A, tetap bisa untuk Toko B",
  consumers=("services/return_identity_service.py:block_policy_on", "services/roll_service.py:_available_rolls_for_order",
             "services/sales_order_helpers.py:reserve_roll_mode_item"),
  permission=("sales_return", "policy"), risk="medium")


E("returns.logistics_vat_enabled", group="retur-koreksi", section="retur", type="bool", default=False, scopes=("global", "entity"),
  label="Catat PPN masukan atas ongkir retur",
  help="Bila aktif, form ongkos kirim retur menampilkan isian PPN dan PPN-nya dicatat terpisah sebagai PPN masukan. "
       "Bila mati, ongkos kirim dicatat utuh sebagai biaya.",
  impact="Jurnal ongkir ditanggung perusahaan: Dr Beban ongkir + Dr PPN masukan / Cr kas-bank-hutang.",
  example="Aktif → ongkir Rp 110.000 dicatat Rp 100.000 beban + Rp 10.000 PPN masukan",
  consumers=("services/return_logistics_service.py:vat_enabled",), permission=("sales_return", "policy"), risk="low")

E("returns.cutloss_treatment_roles", group="retur-koreksi", section="retur", type="list", default=["md", "md_quality"], scopes=("global", "entity"),
  label="Siapa memutus potongan cacat: BS/dibuang",
  help="Peran yang boleh memutuskan potongan kain cacat hasil retur masuk barang sisa (BS) atau dibuang. Admin dan "
       "manajer selalu boleh.",
  impact="Peran lain tetap bisa mencatat jumlah cacat, tetapi pilihan BS/Dibuang dan tombol 'Proses potongan' "
         "ditolak.",
  example="MD dan MD Quality → keduanya yang memutus BS atau dibuang",
  consumers=("services/return_cutloss_split_service.py:assert_can_choose",), permission=("sales_return", "policy"), risk="low",
  # PR-T2 (K-47) — kini izin `sales_return.treat_cutloss`; nilai kunci ini dibaca sekali oleh migrasi pemasangan unit itu.
  status="not_used", not_used_reason="Diatur di Peran & Hak Akses › Pesanan Penjualan (Pilih potongan cacat: masuk BS atau dibuang)",
  items="roles")


# ═══════════════════════════════════════════════════════════════════════════
# KF-T2 — BATAS RETUR UMUM (dulu panel "Asumsi retur" yang menulis `PUT /api/settings` langsung ke dokumen global,
# tanpa riwayat). Kunci tersimpan di jalur yang sama (`system_settings{scope:"global"}.returns.*`), jadi nilai lama
# terbaca sebagai lapisan "pengaturan lama" tanpa migrasi. Dibaca semua pengguna (`sensitif_baca=False`): layar Kebijakan
# Retur menampilkan batas umum bagi yang tidak membuka Pusat Pengaturan. Diubah pemegang `sales_return.policy`.
# ═══════════════════════════════════════════════════════════════════════════
_RETUR_PERM = ("sales_return", "policy")

E("returns.customer_window_days", group="retur-koreksi", section="retur", type="duration", default=21, min=1, max=365, step=1, unit="hari",
  scopes=G, sensitif_baca=False, permission=_RETUR_PERM, risk="medium",
  label="Batas retur pelanggan sejak surat jalan",   # KF-T2 — ≤ 45 huruf (standar §2.1); satuan "hari" tampil di kartu
  help="Pelanggan boleh mengajukan retur sampai sekian hari sesudah tanggal surat jalan. Kebijakan retur per kategori "
       "atau pelanggan boleh menimpa angka ini.",
  impact="Retur yang diajukan lewat batas ini ditandai terlambat; kebijakan retur baru memakai angka ini sebagai "
         "jendela awal.",
  example="21 hari → surat jalan 1 Maret, retur masih boleh diajukan sampai 22 Maret",
  consumers=("services/return_policy_service.py:return_assumptions",))

E("returns.supplier_window_days", group="retur-koreksi", section="retur", type="duration", default=21, min=1, max=365, step=1, unit="hari",
  scopes=G, sensitif_baca=False, permission=_RETUR_PERM, risk="medium",
  label="Batas retur ke pemasok sejak barang diterima",
  help="Klaim ke pemasok harus dikirim sebelum sekian hari sejak roll diterima gudang.",
  impact="Menentukan tenggat klaim retur ke pemasok yang tampil di retur dan disposisi barang.",
  example="21 hari → roll diterima 1 Maret, klaim ke pemasok paling lambat 22 Maret",
  consumers=("services/return_policy_service.py:return_assumptions",))

E("returns.supplier_reminder_days", group="retur-koreksi", section="retur", type="duration", default=3, min=0, max=60, step=1, unit="hari",
  scopes=G, sensitif_baca=False, permission=_RETUR_PERM, risk="medium",
  label="Ingatkan sebelum batas retur pemasok habis",
  help="Pengingat dikirim sekian hari sebelum batas. 0 = tanpa pengingat.",
  impact="Mengubah kapan PT pemasok menerima pengingat klaim retur yang hampir lewat batas.",
  example="3 hari → batas 22 Maret, pengingat dikirim mulai 19 Maret",
  consumers=("services/return_policy_service.py:return_assumptions",))

E("returns.bill_first", group="retur-koreksi", section="retur", type="bool", default=True,
  scopes=G, sensitif_baca=False, permission=_RETUR_PERM, risk="medium",
  label="Potong tagihan pesanan asal lebih dulu",
  help="Nilai retur dipakai mengurangi tagihan pesanan asal; sisanya baru dikembalikan atau menjadi saldo.",
  impact="Bila dimatikan, nilai retur langsung dikembalikan atau menjadi saldo walau tagihan pesanan asal masih terbuka.",
  example="Ya → retur Rp 500.000 atas pesanan bersisa tagihan Rp 300.000: Rp 300.000 memotong tagihan, "
          "Rp 200.000 dikembalikan",
  consumers=("services/return_policy_service.py:return_assumptions",))

E("returns.grade_price_factors", group="retur-koreksi", section="retur", type="table", row_shape="map",
  default={"A": 100, "A1": 95, "A2": 90, "B": 70, "B1": 60, "C": 40, "BS": 10},
  scopes=G, sensitif_baca=False, permission=_RETUR_PERM, risk="medium",
  label="Harga per grade (% dari harga produk)",
  help="Dasar menghitung kerugian saat barang retur turun grade: selisih persen grade lama dan baru dikali harga daftar.",
  impact="Mengubah nilai kerugian turun grade yang dijurnal saat barang retur dilepas dari karantina dengan grade baru.",
  example="A 100 %, B 70 % → roll harga daftar Rp 50.000 turun dari A ke B: rugi Rp 15.000 per satuan "
          "(paling banyak nilai buku roll)",
  consumers=("services/return_grade_impairment.py:grade_factors",))
