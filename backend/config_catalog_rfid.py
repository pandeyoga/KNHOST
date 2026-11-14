"""PREP-H — masa simpan bukti mentah gate RFID V2 (job malam `rfid_evidence_retention`).

Keputusan lintasan, klaim crossing, sesi dokumen, kasus antrean periksa, buku transaksi gate, dan koreksi klaim
TIDAK PERNAH dihapus — setelan di sini hanya untuk bukti mentah (ringkasan bacaan per tag × antena, tepi
photo-eye, event mentah) yang sudah diarsipkan ke berkas terkompresi di penyimpanan lokal server.
"""
from config_registry import E

_G = ("global",)
_C = ("services/rfid_v2_retention.py:settings",)

E("rfid.evidence_retention_mode", group="sistem", section="rfid-proses", type="enum", default="archive", scopes=_G,
  options=({"value": "archive", "label": "Arsipkan ke berkas lalu hapus dari database"},
           {"value": "dry_run", "label": "Uji coba — hanya hitung, tidak mengubah apa pun"},
           {"value": "off", "label": "Mati — bukti disimpan selamanya di database"}),
  label="Bukti gerbang RFID: simpan atau arsipkan",
  help="Catatan mentah tiap roll yang lewat gerbang RFID dipakai untuk memeriksa kasus. Sesudah masa simpan, "
       "catatan dipindah ke arsip (masih bisa dibuka) agar sistem tidak makin berat.",
  impact="'Mati' = database tumbuh ±0,3–0,5 GB per bulan pada 6.000 roll/hari. 'Uji coba' = job hanya "
         "melaporkan jumlah yang akan diarsipkan di riwayat job.",
  example="Arsipkan · masa simpan 90 hari → bukti lintasan 12 Agustus diarsipkan pada malam 10 November",
  consumers=_C, risk="medium")

E("rfid.evidence_retention_days", group="sistem", section="rfid-proses", type="int", default=90, min=7, max=3650, step=1,
  unit="hari", scopes=_G,
  label="Bukti gerbang RFID disimpan selama",
  help="Catatan mentah yang lebih tua dari sekian hari dipindah ke arsip. Catatan yang masih terkait kasus terbuka "
       "tidak diarsipkan.",
  impact="Lebih pendek = database lebih kecil, tetapi unduh bukti lintasan lama harus dari berkas arsip.",
  example="90 → keluhan pelanggan sampai 3 bulan masih bisa diperiksa langsung di ERP",
  consumers=_C, risk="medium", related=("rfid.evidence_retention_mode",))

E("rfid.legacy_reads_retention_days", group="sistem", section="rfid-proses", type="int", default=180, min=7, max=3650, step=1,
  unit="hari", scopes=_G,
  label="Catatan gerbang lama disimpan selama",
  help="Catatan dari alat baca gerbang model lama yang lebih tua dari sekian hari dipindah ke arsip.",
  impact="Riwayat bacaan gate lama di linimasa roll hanya menampilkan bacaan dalam masa simpan.",
  example="180 → bacaan gate lama lebih dari 6 bulan dipindah ke berkas arsip",
  consumers=_C, risk="low", related=("rfid.evidence_retention_mode",))
