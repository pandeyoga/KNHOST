"""PREP-H — masa simpan bukti mentah gate RFID V2 (job malam `rfid_evidence_retention`).

Keputusan lintasan, klaim crossing, sesi dokumen, kasus antrean periksa, buku transaksi gate, dan koreksi klaim
TIDAK PERNAH dihapus — setelan di sini hanya untuk bukti mentah (ringkasan bacaan per tag × antena, tepi
photo-eye, event mentah) yang sudah diarsipkan ke berkas terkompresi di penyimpanan lokal server.
"""
from config_registry import E

_G = ("global",)
_C = ("services/rfid_v2_retention.py:settings",)

E("rfid.evidence_retention_mode", group="stok-satuan", type="enum", default="archive", scopes=_G,
  options=({"value": "archive", "label": "Arsipkan ke berkas lalu hapus dari database"},
           {"value": "dry_run", "label": "Uji coba — hanya hitung, tidak mengubah apa pun"},
           {"value": "off", "label": "Mati — bukti disimpan selamanya di database"}),
  label="Masa simpan bukti gate RFID — mode",
  help="Bukti mentah tiap lintasan gate (bacaan per tag & antena, sinar photo-eye) dipakai untuk memeriksa "
       "kasus. Sesudah masa simpan, bukti dipindah ke berkas arsip terkompresi di server (bisa dibuka lagi), "
       "lalu dihapus dari database agar database tidak terus membesar. Keputusan lintasan & catatan lewat roll "
       "tetap disimpan.",
  impact="'Mati' = database tumbuh ±0,3–0,5 GB per bulan pada 6.000 roll/hari. 'Uji coba' = job hanya "
         "melaporkan jumlah yang akan diarsipkan di riwayat job.",
  example="archive → bukti lintasan 12 Agustus diarsipkan pada malam 10 November (90 hari)",
  consumers=_C, risk="medium")

E("rfid.evidence_retention_days", group="stok-satuan", type="int", default=90, min=7, max=3650, step=1,
  unit="hari", scopes=_G,
  label="Masa simpan bukti gate RFID (hari)",
  help="Bukti mentah lintasan yang lebih tua dari ini diarsipkan lalu dihapus dari database. Lintasan yang masih "
       "punya kasus antrean periksa terbuka atau transaksi gate yang belum tuntas TIDAK diarsipkan.",
  impact="Lebih pendek = database lebih kecil, tetapi unduh bukti lintasan lama harus dari berkas arsip.",
  example="90 → keluhan pelanggan sampai 3 bulan masih bisa diperiksa langsung di ERP",
  consumers=_C, risk="medium", related=("rfid.evidence_retention_mode",))

E("rfid.legacy_reads_retention_days", group="stok-satuan", type="int", default=180, min=7, max=3650, step=1,
  unit="hari", scopes=_G,
  label="Masa simpan bacaan gate lama (hari)",
  help="Bacaan gate jalur lama (reader sebelum U300 V2) yang lebih tua dari ini diarsipkan lalu dihapus. "
       "Bacaan handheld tidak terpengaruh.",
  impact="Riwayat bacaan gate lama di linimasa roll hanya menampilkan bacaan dalam masa simpan.",
  example="180 → bacaan gate lama lebih dari 6 bulan dipindah ke berkas arsip",
  consumers=_C, risk="low", related=("rfid.evidence_retention_mode",))
