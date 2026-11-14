"""FASE G-9 — Katalog konfigurasi **PUSAT KASUS KEUANGAN** (Finance Exception Desk).

Kasus keuangan adalah tempat uang "nyangkut": salah transfer, bayar dobel, giro ditolak,
dana tak dikenal. Aturannya tidak boleh jadi angka sihir di dalam kode — kalau SLA-nya
24 jam atau ambang persetujuannya Rp 5 juta, pemilik usaha harus bisa mengubahnya sendiri
dari Pusat Pengaturan tanpa menunggu rilis baru.

Semua kunci di sini dikonsumsi `services/finance_case_service.py` (+ `_actions`).
"""
from config_registry import E

G = ("global", "entity")

E("case.sla_hours", group="bank-kasus", section="kasus", type="int", default=24, min=1, max=720, step=1,
  unit="jam", scopes=G,
  label="Batas waktu penyelesaian kasus",
  help="Berapa jam sebuah kasus keuangan boleh belum selesai sebelum dianggap terlambat. Kasus terlambat ditandai "
       "merah dan bisa dinaikkan ke atasan.",
  impact="Semakin kecil, semakin cepat kasus terlihat terlambat — antrean jadi lebih disiplin.",
  example="Batas 24 jam · kasus dibuka kemarin 09.00 dan belum selesai → TERLAMBAT",
  consumers=("services/finance_case_service.py:policy",), risk="low",   # KF-T2 — dulu `sla_of` (tidak ada)
  related=("case.sla_hours_high", "case.escalate_on_sla_breach"))

E("case.sla_hours_high", group="bank-kasus", section="kasus", type="int", default=8, min=1, max=720, step=1,
  unit="jam", scopes=G,
  label="Batas waktu untuk kasus bernominal besar",
  help="Kasus yang nominalnya di atas 'Ambang kasus bernominal besar' memakai batas waktu "
       "yang lebih pendek karena risikonya lebih besar.",
  impact="Uang besar tidak boleh menunggu selama uang kecil.",
  example="SLA besar 8 jam · kasus Rp 50.000.000 dibuka 09:00 → terlambat setelah 17:00",
  consumers=("services/finance_case_service.py:policy",), risk="low",   # KF-T2 — dulu `sla_of` (tidak ada)
  related=("case.high_amount_threshold",))

E("case.high_amount_threshold", group="bank-kasus", section="kasus", type="money", default=10000000,
  min=0, step=500000, unit="Rp", scopes=G,
  label="Batas kasus bernominal besar",
  help="Kasus dengan nominal dipertaruhkan di atas angka ini dianggap prioritas tinggi: batas waktunya lebih pendek "
       "dan urutannya di atas. Isi 0 = tidak ada kasus prioritas tinggi karena nominal.",
  impact="Menentukan kasus mana yang naik ke atas antrean.",
  example="Ambang Rp 10.000.000 · kasus Rp 25.000.000 → prioritas TINGGI",
  consumers=("services/finance_case_service.py:policy",), risk="low")

E("case.require_evidence", group="bank-kasus", section="kasus", type="bool", default=True, scopes=G,
  label="Wajib lampirkan bukti sebelum kasus ditutup",
  help="Untuk jenis kasus yang menyangkut klaim pihak lain (mis. transfer dari nama pihak "
       "ketiga, transfer ke rekening pribadi karyawan), penyelesaian tidak boleh dilakukan "
       "tanpa lampiran bukti seperti foto bukti transfer atau surat pernyataan.",
  impact="Kalau dinyalakan, tombol Selesaikan menolak kasus tanpa lampiran.",
  example="Nyala · kasus 'Transfer dari nama pihak ketiga' tanpa lampiran → ditolak",
  consumers=("services/finance_case_service.py:_assert_evidence",), risk="medium")

E("case.require_approval_above", group="bank-kasus", section="kasus", type="money", default=5000000,
  min=0, step=500000, unit="Rp", scopes=G,
  label="Kasus besar wajib disetujui mulai",
  help="Kasus yang penyelesaiannya memindahkan uang lebih besar dari angka ini hanya boleh ditutup oleh peran "
       "penyetuju atau admin. Isi 0 = semua kasus boleh ditutup petugas tanpa persetujuan.",
  impact="Menaikkan angka ini mempercepat kerja tetapi mengurangi kontrol berlapis.",
  example="Ambang Rp 5.000.000 · pengembalian dana Rp 7.500.000 → wajib Manajer/admin",
  consumers=("services/finance_case_service.py:policy",), risk="high",
  related=("case.approver_role", "case.refund_max_amount"))

E("case.approver_role", group="bank-kasus", section="kasus", type="enum", default="manager", scopes=G,
  options=[{"value": "manager", "label": "Manajer"}, {"value": "admin", "label": "Admin"}],
  label="Peran penyetuju penyelesaian kasus",
  help="Siapa yang berwenang menutup kasus yang nominalnya di atas ambang persetujuan.",
  impact="Menentukan siapa yang boleh menutup kasus besar.",
  example="Manajer · pengembalian dana Rp 7.500.000 hanya bisa ditutup Manajer atau admin",
  consumers=("services/finance_case_service.py:policy",), risk="high")

E("case.refund_max_amount", group="bank-kasus", section="kasus", type="money", default=25000000,
  min=0, step=1000000, unit="Rp", scopes=G,
  label="Batas pengembalian dana oleh penyetuju",
  help="Nominal pengembalian dana terbesar yang masih boleh diputus peran penyetuju. Di atas ini wajib Admin "
       "(Direksi). 0 = tanpa batas.",
  impact="Menjaga uang keluar besar tetap di tangan pemilik keputusan tertinggi.",
  example="Batas Rp 25.000.000 · pengembalian dana Rp 40.000.000 oleh Manajer → ditolak, harus admin",
  consumers=("services/finance_case_service.py:policy",), risk="high")

E("case.duplicate_window_days", group="bank-kasus", section="kasus", type="int", default=7, min=1, max=90, step=1,
  unit="hari", scopes=G,
  label="Jendela deteksi pembayaran dobel",
  help="Dua kwitansi pelanggan yang sama dengan nominal sama di dalam jendela hari ini "
       "dicurigai sebagai pembayaran dobel dan otomatis dibuatkan kasus.",
  impact="Semakin lebar, semakin banyak dugaan dobel yang tertangkap (bisa lebih banyak alarm).",
  example="Jendela 7 hari · Rp 3.750.000 dari pelanggan yang sama pada 1 & 5 Juli → 1 kasus",
  consumers=("services/finance_case_service.py:policy",), risk="medium")

E("case.holding_case_after_days", group="bank-kasus", section="kasus", type="int", default=3, min=1, max=365, step=1,   # KF-T3 — 0 dulu → 3
  unit="hari", scopes=G,
  label="Dana titipan jadi kasus setelah (hari)",
  help="Dana masuk tak dikenal yang sudah menganggur selama sekian hari otomatis dibuatkan kasus keuangan, supaya "
       "ada penanggung jawabnya. Bedanya dengan “Dana titipan ditandai tua setelah”: yang itu hanya memberi tanda "
       "di layar Rekonsiliasi Bank.",
  impact="Semakin kecil, semakin cepat uang tak dikenal ditindaklanjuti orang.",
  example="3 hari · titipan Rp 5.131.200 masuk 26 Juli, pada 29 Juli otomatis jadi kasus",
  consumers=("services/finance_case_service.py:policy",), risk="medium",
  related=("bank.holding_max_age_days",))

E("case.auto_bank_charge_max", group="bank-kasus", section="kasus", type="money", default=50000, min=0, step=5000,
  unit="Rp", scopes=G,
  label="Selisih biaya bank yang selesai otomatis",
  help="Bila uang yang masuk kurang dari tagihan hanya sebesar biaya transfer (di bawah angka ini), kasusnya "
       "diselesaikan tanpa persetujuan dan selisihnya dicatat sebagai biaya administrasi bank. Isi 0 = selisih "
       "biaya transfer selalu perlu persetujuan.",
  impact="Membebaskan keuangan dari kasus receh, tetapi tetap berjurnal dan berlabel.",
  example="Batas Rp 50.000 · kurang Rp 6.500 karena biaya transfer → selesai otomatis",
  consumers=("services/finance_case_service.py:policy",
            "services/finance_case_service.py:resolve"), risk="medium")

E("case.escalate_on_sla_breach", group="bank-kasus", section="kasus", type="bool", default=True, scopes=G,
  label="Naikkan kasus terlambat ke atasan",
  help="Kasus yang melewati batas waktu diberitahukan ke Manajer, lalu ke admin. Bila dimatikan, kasus terlambat "
       "hanya terlihat di daftar.",
  impact="Kalau dimatikan, kasus terlambat hanya terlihat di Inbox tanpa memberi tahu siapa pun.",
  example="Nyala · kasus lewat 24 jam → notifikasi 'ESKALASI: Kasus keuangan terlambat'",
  consumers=("services/finance_case_service.py:policy",), risk="low")

E("case.auto_scan_enabled", group="bank-kasus", section="kasus", type="bool", default=True, scopes=G,
  label="Buat kasus otomatis dari temuan sistem",
  help="Sistem memindai titipan dana yang menganggur dan pembayaran yang terlihat dobel, "
       "lalu membuat kasusnya sendiri. Kalau dimatikan, kasus hanya bisa dibuat manual.",
  impact="Mematikan ini membuat antrean bergantung pada kerajinan orang mengetik kasus.",
  example="Nyala · pemindai harian menemukan 1 titipan tua → 1 kasus baru bernomor KSC/CASE-00001",
  consumers=("services/finance_case_service.py:policy",), risk="medium")
