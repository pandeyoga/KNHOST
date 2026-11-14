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

# PK-36 (IC-06, K-02) — akun kontrol (piutang, hutang, persediaan, antar-PT) hanya berubah lewat dokumennya. Bawaan
# "tolak" menyimpang dari "bawaan = perilaku hari ini" (02 §2.1) karena keputusan pemilik K-02 menyebut bawaannya.
# Izin pengubah `accounting.manage` (`accounting.configure` belum ada di matriks izin — ASUMSI unit).
E("gl.jurnal_manual_akun_kontrol", group="pajak-pembukuan", section="tutup-buku", type="enum", default="tolak",
  options=({"value": "tolak", "label": "Tolak"}, {"value": "izinkan", "label": "Izinkan"}),
  scopes=G,
  label="Jurnal manual ke akun kontrol",
  help="Akun piutang, hutang, persediaan, dan antar-PT dijaga dokumennya. Pilih Tolak supaya akun itu tidak bisa "
       "diisi lewat jurnal manual, reklasifikasi suspense, atau pembalikan manual.",
  impact="Bila diizinkan, saldo buku besar bisa berbeda dari daftar piutang, hutang, stok, atau saldo antar-PT tanpa "
         "ada dokumen yang menjelaskannya.",
  example="Tolak · jurnal manual Dr 1-1200 Piutang Rp 500.000 → ditolak, diarahkan ke Nota Kredit",
  consumers=("services/gl_service.py:assert_no_control_accounts",
             "services/gl_service.py:list_accounts"),
  risk="high", requires_reason=True,
  permission=("accounting", "manage"))

# PK-37 (GL-05, keputusan K-03 "Mengunci") — langkah PERIKSA dokumen/pembayaran/mutasi stok di periode tertutup.
E("periode.kunci_dokumen", group="pajak-pembukuan", section="tutup-buku", type="bool",
  default=True, scopes=G,
  label="Periode tertutup mengunci dokumen",
  help="Bila menyala, dokumen, pembayaran, dan mutasi stok yang bertanggal di periode yang sudah ditutup ditolak "
       "sebelum disimpan. Bila mati, dokumen tetap tersimpan dan hanya jurnalnya yang ditolak.",
  # Teks spesifikasi menyebut panel "Posting Gagal"; kata 'posting' ditolak penjaga INV-CFG-TXT → disebut "jurnal gagal".
  impact="Mati = dokumen bisa tersimpan tanpa jurnal, lalu jurnalnya harus diselesaikan dari daftar jurnal gagal di "
         "menu Keuangan.",
  example="Menyala · Oktober sudah ditutup · penyesuaian stok bertanggal 30 Okt → ditolak, stok tidak berubah",
  consumers=("services/book_date.py:periksa_periode_dokumen",),
  risk="high", requires_reason=True,
  permission=("accounting", "manage"),
  related=("periode.unlock_window_hours", "periode.max_days_after_close"))

# PK-22 (FY-02, keputusan K-13) — tanggal buku jurnal periodik (gaji, penyusutan, akrual insentif). Teks pilihan, dampak,
# dan contoh spesifikasi memakai kata "diposting"/"hari posting" — ditolak penjaga INV-CFG-TXT (kata teknis) → "dibuat"
# / "dicatat ke buku besar". Nilai pilihan (`hari_posting`) tetap sama dengan spesifikasi.
E("gl.tanggal_jurnal_periodik", group="pajak-pembukuan", section="tutup-buku", type="enum", default="akhir_periode",
  options=({"value": "akhir_periode", "label": "Hari terakhir periodenya"},
           {"value": "hari_posting", "label": "Hari saat jurnalnya dibuat"}),
  scopes=G,
  label="Tanggal jurnal gaji, penyusutan, dan insentif",
  help="Menentukan tanggal buku untuk jurnal yang dibuat per periode: gaji, penyusutan aset, dan akrual insentif.",
  impact="Bila diubah ke hari jurnal dibuat, beban bulan lalu yang dicatat ke buku besar bulan ini masuk ke laporan "
         "bulan ini.",
  example="Gaji Oktober dicatat ke buku besar 3 November → jurnal bertanggal 31 Oktober",
  consumers=("services/periodic_posting.py:journal_date",),
  risk="high", requires_reason=True,
  permission=("accounting", "manage"))
