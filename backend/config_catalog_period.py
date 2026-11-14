"""FASE G-5 — Katalog konfigurasi **UNLOCK PERIODE TERTUTUP**.

Pemilik: *"Bangun izin buka periode tertutup yang wajib dua orang dan menutup
sendiri saat waktunya habis."* Semua ambang di sini dikonsumsi oleh
`services/period_unlock_service.py` (jendela unlock & batas mundur), sehingga
dapat diubah admin dari Pusat Pengaturan tanpa deploy.
"""
from config_registry import E

G = ("global", "entity")

E("periode.unlock_window_hours", group="pajak-pembukuan", section="tutup-buku", type="int",
  default=24, min=1, max=168, step=1, unit="jam", scopes=G,
  label="Lama periode dibuka kembali",
  help="Setelah usul buka periode disetujui, periode hanya terbuka selama sekian jam lalu terkunci lagi dengan "
       "sendirinya.",
  impact="Menentukan berapa lama koreksi mundur boleh dicatat sebelum periode terkunci lagi.",
  example="24 jam · disetujui 09:00 → periode terkunci lagi otomatis besok 09:00",
  consumers=("services/period_unlock_service.py:approve_request",
             "services/period_unlock_service.py:reclose_expired"),
  risk="high", requires_reason=True,
  related=("periode.max_days_after_close",))

E("periode.max_days_after_close", group="pajak-pembukuan", section="tutup-buku", type="int",
  default=7, min=0, max=3650, step=1, unit="hari", scopes=G,
  label="Batas usia periode yang boleh dibuka lagi",
  help="Periode yang sudah ditutup lebih lama dari sekian hari tidak boleh diusulkan dibuka lagi. Isi 0 bila tidak "
       "ingin membatasi (tidak disarankan).",
  impact="Mencegah membuka periode lama yang laporannya sudah beredar/diaudit.",
  example="7 hari · periode ditutup 20 hari lalu → usul DITOLAK (di luar batas mundur)",
  consumers=("services/period_unlock_service.py:request_unlock",),
  risk="high",
  related=("periode.unlock_window_hours",))
