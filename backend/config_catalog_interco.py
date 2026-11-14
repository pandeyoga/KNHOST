"""FASE G-6 — Katalog konfigurasi **ANTAR ENTITAS** (jual-beli antar-PT dalam grup).

Kenapa configurable: pemilik menegaskan (keputusan 2026-07-30):
  1. **Harga antar-PT `fixed_price` dari kontrak internal** (mode bawaan).
     Sistem TIDAK BOLEH menebak harga (mis. WAC diam-diam).
  2. **PPN internal berbeda per PT** — mode ber-scope entity: `ikut_pkp` (bawaan) ·
     `tanpa_ppn` · `dengan_ppn`. Bila ber-PPN, PPN keluaran penjual == PPN masukan
     pembeli (INV-IC-05).
  3. **Settlement sewaktu-waktu** lewat tombol (tanpa job penjadwal). Config opsional
     `settlement_reminder_days` memicu PENGINGAT bila saldo menganggur > N hari.

Semua kunci di sini dikonsumsi `services/interco_service.py`.
"""
from config_registry import E

G = ("global", "entity")

# KP-T4 — alasan baku kunci persetujuan yang pindah ke Aturan Persetujuan.
_KPT4_TIDAK_DIPAKAI = ("Dipindah ke Aturan Persetujuan (Pengaturan › Persetujuan › Aturan Persetujuan). Nilai terakhirnya hanya membentuk aturan bawaan selama aturan belum disimpan.")

E("antar_entitas.pricing_mode", group="pajak-pembukuan", section="antar-pt", type="enum", default="fixed_price",
  scopes=G,
  options=[
      {"value": "fixed_price", "label": "Harga tetap dari kontrak internal"},
      {"value": "at_cost", "label": "Sesuai HPP penjual (tanpa margin)"},
      {"value": "cost_plus_pct", "label": "HPP penjual + persen margin"},
  ],
  label="Cara menentukan harga jual antar-PT",
  help="Harga barang saat satu PT menjual ke PT lain: harga tetap dari kontrak internal (ditolak bila belum ada "
       "harganya), sebesar biaya pokok penjual, atau biaya pokok ditambah persen margin.",
  impact="Menentukan apakah margin antar-PT direalisasi & apakah dokumen ditolak saat "
         "harga kontrak belum ada.",
  example="Harga tetap · kontrak KSC↔Kanda: PRD-001 = Rp 25.000/yard → PO internal memakai angka itu; barang tanpa "
          "harga kontrak → ditolak",
  consumers=("services/interco_service.py:create",), risk="high",
  related=("antar_entitas.ppn_mode", "antar_entitas.settlement_reminder_days"))

E("antar_entitas.ppn_mode", group="pajak-pembukuan", section="antar-pt", type="enum", default="ikut_pkp",
  scopes=G,
  options=[
      {"value": "ikut_pkp", "label": "Mengikuti status PKP PT penjual"},
      {"value": "tanpa_ppn", "label": "Tanpa PPN"},
      {"value": "dengan_ppn", "label": "Dengan PPN (paksa)"},
  ],
  label="PPN untuk jual-beli antar-PT",
  help="Mengikuti status PKP PT penjual, selalu tanpa PPN, atau selalu ber-PPN (penjual menerbitkan faktur pajak, "
       "pembeli mencatat PPN masukan).",
  impact="Menentukan apakah Faktur Pajak internal diterbitkan dan apakah PPN keluaran penjual sama besar dengan PPN "
         "masukan pembeli.",
  example="Ikut status PKP penjual · penjual PT KSC (PKP) · pembeli CV Kanda → ber-PPN. Penjual bukan PKP → tanpa "
          "PPN",
  consumers=("services/interco_service.py:create",), risk="high",
  related=("antar_entitas.pricing_mode",))

E("antar_entitas.approval_threshold_rupiah", group="pajak-pembukuan", section="antar-pt", type="money",
  default=100000000, min=0, step=1000000, unit="Rp", scopes=G,
  label="Transaksi antar-PT bernilai besar mulai",
  help="Transaksi antar-PT dengan nilai di atas angka ini harus disetujui peran yang lebih tinggi.",
  impact="Menentukan kapan penjualan internal harus naik ke admin (pemisahan tugas).",
  example="Ambang Rp 100.000.000 · transaksi Rp 250.000.000 → wajib disetujui admin",
  consumers=("services/approval_policy_service.py:default_rows_for",), risk="high",
  related=("antar_entitas.approval_role", "antar_entitas.high_value_approval_role"),
  # KP-T4 — isi kunci ini pindah ke tabel kebijakan persetujuan (`approval_policies`).
  status="not_used", not_used_reason=_KPT4_TIDAK_DIPAKAI)

E("antar_entitas.approval_role", group="pajak-pembukuan", section="antar-pt", type="enum", default="manager",
  scopes=G,
  options=[{"value": "manager", "label": "Manajer"}, {"value": "admin", "label": "Admin"}],
  label="Peran penyetuju transaksi antar-PT",
  help="Peran minimal yang boleh menyetujui transaksi antar-PT bernilai di bawah ambang.",
  impact="Menentukan siapa yang boleh melepas penjualan internal.",
  example="Manajer · transaksi Rp 30.000.000 bisa disetujui Manajer",
  consumers=("services/approval_policy_service.py:default_rows_for",), risk="high",
  # KP-T4 — isi kunci ini pindah ke tabel kebijakan persetujuan (`approval_policies`).
  status="not_used", not_used_reason=_KPT4_TIDAK_DIPAKAI)

E("antar_entitas.high_value_approval_role", group="pajak-pembukuan", section="antar-pt", type="enum",
  default="admin", scopes=G,
  options=[{"value": "manager", "label": "Manajer"}, {"value": "admin", "label": "Admin"}],
  label="Penyetuju transaksi antar-PT bernilai besar",
  help="Peran minimal yang menyetujui transaksi antar-PT di atas batas bernilai besar.",
  impact="Uang besar tidak boleh dilepas oleh wewenang yang sama dengan uang kecil.",
  example="Admin · transaksi Rp 250.000.000 ditolak bila hanya disetujui Manajer",
  consumers=("services/approval_policy_service.py:default_rows_for",), risk="high",
  # KP-T4 — isi kunci ini pindah ke tabel kebijakan persetujuan (`approval_policies`).
  status="not_used", not_used_reason=_KPT4_TIDAK_DIPAKAI)

E("antar_entitas.settlement_reminder_days", group="pajak-pembukuan", section="antar-pt", type="int", default=30,
  min=0, max=365, step=1, unit="hari", scopes=G,
  label="Ingatkan saldo antar-PT yang diam (hari)",
  help="Bila saldo utang-piutang antara dua PT tidak bergerak lebih dari sekian hari, sistem mengirim pengingat "
       "untuk melunasinya. Tidak memaksa jadwal. Isi 0 dibaca sistem sebagai 30 hari.",
  impact="Membuat saldo lama antar-PT terlihat tanpa memaksa jadwal.",
  example="30 hari · saldo pasangan KSC↔KANDA tidak bergerak 45 hari → pengingat muncul",
  consumers=("services/interco_reminder.py:job_interco_settlement_reminder",
             "services/interco_service.py:list_accounts"), risk="low")

E("antar_entitas.ppn_rate_percent", group="pajak-pembukuan", section="antar-pt", type="pct", default=0.0,
  min=0, max=100, step=0.5, unit="%", scopes=G,
  label="Tarif PPN khusus antar-PT (0 = ikut umum)",
  help="Isi 0 agar PPN antar-PT mengikuti pengaturan pajak penjualan PT penjual. Isi angka lain hanya bila perlu "
       "tarif khusus.",
  impact="Menentukan besar PPN keluaran penjual & PPN masukan pembeli internal.",
  example="0 → 12% × DPP 11/12 · harga Rp 10.000.000 → DPP Rp 9.166.667, PPN Rp 1.100.000",
  consumers=("services/interco_service.py:_interco_rate",), risk="medium")


# ── KF-T2 — jadwal bayar antar-PT (LN-024 / KLX-03). Dulu form "Cutoff" di tab Jadwal Bayar yang menulis `PUT /api/settings`
# langsung (tanpa riwayat) dan dua sakelar yang tidak punya layar sama sekali. Jalur simpan sama
# (`system_settings.interco_payment.*`) sehingga nilai lama terbaca sebagai lapisan "pengaturan lama". Wewenang tetap
# `entity.update` (sama dengan syarat `PUT /api/settings` hari ini).
_IC_PAY_PERM = ("entity", "update")

E("interco_payment.allow_netting", group="pajak-pembukuan", section="antar-pt", type="bool", default=False, scopes=G,
  sensitif_baca=False, permission=_IC_PAY_PERM, risk="medium",
  label="Izinkan saling hapus hutang antar-PT",
  help="Bila tidak, tiap transaksi antar-PT dibayar penuh lewat transfer atau kas.",
  impact="Bila diizinkan, pelunasan antar-PT boleh memakai metode saling hapus (netting) untuk PT pembayar ini.",
  example="Tidak → pelunasan KSC ke Kanda dengan metode saling hapus ditolak; pilih transfer atau kas",
  consumers=("services/interco_service.py:payment_settings",))

E("interco_payment.require_full_payment", group="pajak-pembukuan", section="antar-pt", type="bool", default=True, scopes=G,
  sensitif_baca=False, permission=_IC_PAY_PERM, risk="medium",
  label="Pembayaran antar-PT harus penuh per transaksi",
  help="Bila ya, pelunasan sebagian ditolak.",
  impact="Bila dimatikan, satu transaksi antar-PT boleh dilunasi bertahap.",
  example="Ya → sisa tagihan Rp 10.000.000 dibayar Rp 4.000.000 → ditolak",
  consumers=("services/interco_service.py:payment_settings",))

E("interco_payment.cutoff_day", group="pajak-pembukuan", section="antar-pt", type="int", default=0, min=0, max=31, step=1, unit="tanggal",
  scopes=G, sensitif_baca=False, permission=_IC_PAY_PERM, risk="medium",
  label="Tanggal tutup tagihan antar-PT",
  help="Transaksi sampai tanggal ini masuk jadwal bayar bulan itu. 0 = belum diatur (jadwal dan pengingat tidak berjalan).",
  impact="Menentukan periode bayar tiap transaksi antar-PT di tab Jadwal Bayar dan kapan pengingat dikirim.",
  example="25 → transaksi 25 Oktober masuk periode Oktober, transaksi 26 Oktober masuk periode November",
  consumers=("services/interco_service.py:payment_settings",))

E("interco_payment.payment_day", group="pajak-pembukuan", section="antar-pt", type="int", default=0, min=0, max=31, step=1, unit="tanggal",
  scopes=G, sensitif_baca=False, permission=_IC_PAY_PERM, risk="medium",
  label="Tanggal bayar antar-PT",
  help="0 = akhir bulan.",
  impact="Menentukan tanggal bayar yang tampil di jadwal dan dasar pengingat bayar antar-PT.",
  example="28 → transaksi periode Oktober jatuh tempo 28 Oktober; 0 → 31 Oktober",
  consumers=("services/interco_service.py:payment_settings",))

E("interco_payment.basis", group="pajak-pembukuan", section="antar-pt", type="enum", default="", scopes=G,
  options=[{"value": "", "label": "Belum diatur"},
           {"value": "receipt", "label": "Tanggal barang diterima"},
           {"value": "invoice", "label": "Tanggal tagihan"},
           {"value": "document", "label": "Tanggal dokumen"}],
  sensitif_baca=False, permission=_IC_PAY_PERM, risk="medium",
  label="Tanggal acuan jadwal bayar antar-PT",
  help="Tanggal mana yang dibandingkan dengan tanggal tutup.",
  impact="Belum diatur = jadwal bayar dan pengingat antar-PT tidak berjalan.",
  example="Tanggal barang diterima · tutup tanggal 25 · barang diterima 26 Oktober → periode November",
  consumers=("services/interco_service.py:payment_settings",))

E("interco_payment.reminder_days", group="pajak-pembukuan", section="antar-pt", type="duration", default=3, min=0, max=30, step=1,
  unit="hari", scopes=G, sensitif_baca=False, permission=_IC_PAY_PERM, risk="medium",
  label="Ingatkan sebelum tanggal bayar antar-PT",   # KF-T2 — ≤ 45 huruf (standar §2.1)
  help="0 = tanpa pengingat.",
  impact="Mengubah kapan finance PT pembayar menerima pengingat bayar antar-PT.",
  example="3 → tanggal bayar 28 Oktober, pengingat dikirim mulai 25 Oktober",
  consumers=("services/interco_service.py:payment_settings",))
