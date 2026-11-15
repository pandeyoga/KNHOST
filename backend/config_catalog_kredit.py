"""CR-T3 (K-27, K-29, K-31) — sembilan kunci gerbang kredit (`docs/blueprint/unit/CR-T3.md`, bagian "Pengaturan").

Semua berlapis grup → PT, risiko tinggi dengan alasan wajib, diubah pemegang izin kredit (`credit_profile.approve`, sama
dengan `ar.default_credit_limit` CR-T1). Bawaan = perilaku hari ini (`00` §4.1): hanya titik "pesanan dibuat" yang
memeriksa, izin kredit tanpa masa berlaku, pesanan tunai tidak ditahan sampai lunas. Komposisi eksposur mengikuti K-31
(pesanan belum dikirim dan giro belum cair ikut dihitung, titipan mengurangi). Menyalakan titik periksa lain, masa
berlaku izin, atau tahan-kirim tunai untuk PT nyata = keputusan pemilik (H5).
"""
from config_registry import E

_GE = ("global", "entity")
_GATE = ("services/credit_gate.py:evaluate",)
_IZIN = {"risk": "high", "requires_reason": True, "permission": ("credit_profile", "approve")}

# ── Titik periksa ────────────────────────────────────────────────────────────────────────────────────────────────────
E("ar.periksa_kredit_pesanan_dibuat", group="uang-masuk", section="kredit", type="bool", default=True, scopes=_GE,
  label="Periksa kredit saat pesanan dibuat",
  help="Pelanggan yang terblokir tidak bisa membuat pesanan tempo. Pesanan bayar penuh sebelum kirim tetap boleh, "
       "barangnya ditahan sampai lunas.",
  impact="Bila dimatikan, tidak ada pemeriksaan kredit saat checkout.",
  example="Plafon Rp 10 jt, eksposur Rp 10,5 jt → pesanan ditolak",
  consumers=_GATE, related=("ar.periksa_kredit_pesanan_diubah", "ar.overdue_block_days"), **_IZIN)

E("ar.periksa_kredit_pesanan_diubah", group="uang-masuk", section="kredit", type="bool", default=False, scopes=_GE,
  label="Periksa kredit saat nilai pesanan naik",
  help="Berlaku saat jumlah ditambah atau termin dilonggarkan lewat koreksi pesanan. Perubahan tetap disimpan.",
  impact="Bila menyala, pesanan yang membuat eksposur melewati plafon ditahan kredit.",
  example="Pesanan Rp 2 jt dinaikkan ke Rp 5 jt → Tahan kredit",
  consumers=_GATE + ("services/credit_gate.py:term_change_allowed",),
  related=("ar.periksa_kredit_pesanan_dibuat",), **_IZIN)

E("ar.periksa_kredit_lepas_gudang", group="uang-masuk", section="kredit", type="bool", default=False, scopes=_GE,
  label="Periksa kredit saat pesanan dilepas ke gudang",
  help="Kredit diperiksa ulang sebelum gudang mulai menyiapkan barang.",
  impact="Bila menyala, pesanan pelanggan yang kini telat atau lewat plafon tidak dilepas ke gudang.",
  example="Telat 20 hari saat dilepas → Tahan kredit",
  consumers=_GATE, related=("ar.periksa_kredit_surat_jalan",), **_IZIN)

E("ar.periksa_kredit_surat_jalan", group="uang-masuk", section="kredit", type="bool", default=False, scopes=_GE,
  label="Periksa kredit saat barang dikirim",
  help="Kredit diperiksa ulang sebelum surat jalan terbit.",
  impact="Bila menyala, barang tidak keluar untuk pelanggan yang terblokir.",
  example="Telat 20 hari saat barang akan dikirim → Tahan kredit",
  consumers=_GATE, related=("ar.periksa_kredit_lepas_gudang",), **_IZIN)

# ── Komposisi eksposur (K-31) ────────────────────────────────────────────────────────────────────────────────────────
E("ar.eksposur_pesanan_belum_kirim", group="uang-masuk", section="kredit", type="bool", default=True, scopes=_GE,
  label="Hitung pesanan belum dikirim dalam eksposur",
  help="Eksposur = piutang barang terkirim ditambah nilai pesanan yang belum dikirim.",
  impact="Bila dimatikan, hanya barang terkirim yang mengurangi sisa plafon.",
  example="Terkirim Rp 6 jt + belum dikirim Rp 2 jt = eksposur Rp 8 jt",
  consumers=_GATE, related=("ar.eksposur_giro_belum_cair", "ar.eksposur_titipan_mengurangi"), **_IZIN)

E("ar.eksposur_giro_belum_cair", group="uang-masuk", section="kredit", type="bool", default=True, scopes=_GE,
  label="Hitung giro belum cair dalam eksposur",
  help="Giro atau cek yang sudah diterima tetapi belum cair di bank tetap dihitung sebagai risiko kredit.",
  impact="Bila dimatikan, giro dianggap lunas saat diterima.",
  example="Giro Rp 3 jt belum cair menambah eksposur Rp 3 jt",
  consumers=_GATE, related=("ar.eksposur_pesanan_belum_kirim",), **_IZIN)

E("ar.eksposur_titipan_mengurangi", group="uang-masuk", section="kredit", type="bool", default=True, scopes=_GE,
  label="Titipan pelanggan mengurangi eksposur",
  help="Uang titipan pelanggan yang belum dipakai mengurangi eksposur.",
  impact="Bila dimatikan, titipan tidak menambah sisa plafon.",
  example="Eksposur Rp 8 jt − titipan Rp 0,5 jt = Rp 7,5 jt",
  consumers=_GATE, related=("ar.eksposur_pesanan_belum_kirim",), **_IZIN)

# ── Izin kredit ──────────────────────────────────────────────────────────────────────────────────────────────────────
E("ar.izin_kredit_masa_berlaku_hari", group="uang-masuk", section="kredit", type="int", default=0, min=0, max=90,
  step=1, unit="hari", scopes=_GE,
  label="Izin kredit berlaku selama (hari)",
  help="Dihitung sejak izin disetujui. 0 = izin tidak kedaluwarsa.",
  impact="Angka di atas 0 membuat izin kredit yang tidak dipakai hangus sesudah sekian hari.",
  example="3 · izin disetujui Senin → hangus Kamis",
  consumers=("services/credit_override_service.py:masa_berlaku",), related=("ar.periksa_kredit_pesanan_dibuat",),
  **_IZIN)

# ── Tahan kirim tunai ────────────────────────────────────────────────────────────────────────────────────────────────
E("finance.tahan_kirim_tunai", group="uang-masuk", section="syarat-bayar", type="bool", default=False, scopes=_GE,
  label="Tahan pengiriman pesanan tunai sampai lunas",
  help="Termin tunai diperlakukan seperti bayar dulu 100 %. Tagihan tunai yang terkirim lewat pengecualian berizin "
       "ikut dihitung sebagai piutang dan telat.",
  impact="Bila menyala, pesanan tunai tidak bisa dikirim sebelum dibayar, kecuali dengan pengecualian berizin.",
  example="Tunai Rp 1 jt belum dibayar → tertahan",
  consumers=("services/credit_gate.py:evaluate", "services/dispatch_payment_gate.py:_tunai_ditahan"),
  related=("finance.dispatch_payment_gate",), **_IZIN)
