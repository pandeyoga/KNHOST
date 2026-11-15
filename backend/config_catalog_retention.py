"""FIX-7 (butir 5) — masa simpan LOG TEKNIS (job malam `log_retention`, `services/log_retention.py`).

Hanya log operasional sekali pakai: riwayat job penjadwal, kotak keluar WhatsApp, klaim ringkasan harian. Jejak audit
bisnis (audit_logs, status_history, jurnal, mutasi stok) TIDAK PERNAH disentuh setelan ini.
"""
from config_registry import E

_G = ("global",)
_C = ("services/log_retention.py:settings",)
# R0 (KF-T3/KF-T8) — empat kunci hari dibaca `settings()` lewat tabel `RULES` tingkat modul (kolom `setting`), jadi
# rujukannya berkas, bukan badan fungsi.
_C_HARI = ("services/log_retention.py",)
_REL = ("ops.log_retention_mode",)

E("ops.log_retention_mode", group="notifikasi", type="enum", default="delete", scopes=_G,
  options=({"value": "delete", "label": "Hapus baris yang lewat masa simpan"},
           {"value": "dry_run", "label": "Uji coba — hanya hitung, tidak menghapus apa pun"},
           {"value": "off", "label": "Mati — log disimpan selamanya"}),
  label="Masa simpan log teknis — mode",
  help="Riwayat job penjadwal, kotak keluar WhatsApp, dan klaim ringkasan harian bertambah ribuan baris per hari. "
       "Job malam 'Masa Simpan Log Teknis' menghapus baris yang lebih tua dari masa simpan di bawah. Jejak audit, "
       "riwayat status dokumen, jurnal, dan mutasi stok tidak pernah dihapus.",
  impact="'Mati' = riwayat job penjadwal tumbuh ±0,5–1 juta baris per tahun (memperlambat layar Penjadwal & "
         "cadangan). 'Uji coba' = job hanya melaporkan jumlah yang akan dihapus di riwayat job.",
  example="delete → riwayat job berhasil yang lebih tua dari 30 hari dihapus tiap malam pukul 03.40 WIB",
  consumers=_C, risk="low")

E("ops.scheduler_runs_retention_days", group="notifikasi", type="int", default=30, min=7, max=3650, step=1,
  unit="hari", scopes=_G,
  label="Masa simpan riwayat job berhasil (hari)",
  help="Baris riwayat job penjadwal yang BERHASIL dan lebih tua dari ini dihapus. Baris terakhir tiap job selalu "
       "disimpan sehingga kolom 'Terakhir jalan' tetap terisi.",
  impact="Lebih pendek = koleksi lebih kecil; riwayat job yang bisa ditelusuri di layar Penjadwal lebih singkat.",
  example="30 → riwayat sebulan terakhir tetap bisa dibuka",
  consumers=_C_HARI, risk="low", related=_REL)

E("ops.scheduler_runs_failed_retention_days", group="notifikasi", type="int", default=90, min=7, max=3650, step=1,
  unit="hari", scopes=_G,
  label="Masa simpan riwayat job gagal (hari)",
  help="Baris riwayat job yang GAGAL disimpan lebih lama untuk penelusuran masalah, lalu dihapus sesudah batas ini.",
  impact="Lebih pendek = jejak galat job lama hilang lebih cepat.",
  example="90 → galat job tiga bulan terakhir masih bisa dibaca",
  consumers=_C_HARI, risk="low", related=_REL)

E("ops.wa_outbox_retention_days", group="notifikasi", type="int", default=90, min=7, max=3650, step=1,
  unit="hari", scopes=_G,
  label="Masa simpan kotak keluar WhatsApp (hari)",
  help="Catatan pesan WhatsApp yang sudah dikirim/gagal dan lebih tua dari ini dihapus. Pesan yang masih antre tidak "
       "dihapus. Kunci anti-dobel berisi tanggal, jadi penghapusan tidak membuat pesan lama terkirim ulang.",
  impact="Lebih pendek = bukti kirim WhatsApp lama tidak bisa dibuka lagi di layar Outbox.",
  example="90 → bukti kirim tiga bulan terakhir tetap ada",
  consumers=_C_HARI, risk="low", related=_REL)

E("ops.digest_claims_retention_days", group="notifikasi", type="int", default=30, min=7, max=3650, step=1,
  unit="hari", scopes=_G,
  label="Masa simpan klaim ringkasan harian (hari)",
  help="Penanda teknis 'ringkasan hari X untuk nomor Y sudah dikirim' (mencegah kirim ganda di hari yang sama). "
       "Sesudah beberapa hari tidak dipakai lagi.",
  impact="Tidak terlihat pengguna; hanya menjaga koleksi teknis tetap kecil.",
  example="30 → klaim lebih dari sebulan dihapus",
  consumers=_C_HARI, risk="low", related=_REL)
