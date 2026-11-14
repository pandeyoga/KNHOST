"""KM-T1 (keputusan K-19, K-20, K-21, K-23) — Katalog konfigurasi **DEFINISI ANGKA INSENTIF** (Meja Insentif).

Empat pilihan per PT yang menentukan arti angka dasar insentif: kapan omzet dihitung, apa yang disebut pencairan, milik
siapa angka penjualan, dan harga pembanding kualitas harga. Nilainya dimiliki Pusat Pengaturan (global → PT); setiap
perubahan nilai PT dicatat sebagai versi baru di `incentive_definitions` oleh
`services/incentive_definitions.py:current_definition`, supaya lembar insentif (KM-T3) bisa memotret versi yang berlaku.
Bawaan = usulan yang disetujui pemilik (`docs/blueprint/01_KEPUTUSAN.md` K-19 … K-23).
"""
from config_registry import E

G = ("global", "entity")
_PEMBACA = ("services/incentive_definitions.py:current_definition",)
_IZIN = ("incentive", "configure")

E("insentif.dasar_omzet", group="harga-diskon", section="komisi", type="enum", default="terkirim",
  options=({"value": "pesanan", "label": "Saat pesanan dibuat"},
           {"value": "terkirim", "label": "Saat barang dikirim"},
           {"value": "lunas", "label": "Saat pesanan lunas"}),
  scopes=G,
  label="Omzet insentif dihitung saat",
  help="Kapan penjualan masuk hitungan omzet sales.",
  impact="Mengubah angka omzet di Capaian sejak versi definisi berikutnya; lembar yang sudah disahkan tidak berubah.",
  example="Pesanan 10 Okt dikirim 3 Nov → Saat barang dikirim: omzet November",
  consumers=_PEMBACA, risk="high", requires_reason=True, permission=_IZIN)

E("insentif.isi_pencairan", group="harga-diskon", section="komisi", type="enum", default="uang_masuk",
  options=({"value": "uang_masuk", "label": "Hanya uang yang masuk"},
           {"value": "semua_baris", "label": "Semua pelunasan"}),
  scopes=G,
  label="Yang dihitung sebagai pencairan",
  help="Hanya uang yang masuk = tunai, transfer, QRIS, giro, deposit, dan titipan bank. Semua pelunasan = ditambah hapus "
       "sisa, nota kredit, saldo kredit, dan kasus keuangan.",
  impact="Mengubah angka uang masuk sales.",
  example="Hapus sisa Rp 500.000 tidak dihitung pada Hanya uang yang masuk",
  consumers=_PEMBACA, risk="high", requires_reason=True, permission=_IZIN)

E("insentif.pemilik_angka", group="harga-diskon", section="komisi", type="enum", default="sales_pesanan",
  options=({"value": "sales_pesanan", "label": "Sales pada pesanan"},
           {"value": "pemilik_pelanggan", "label": "Sales penanggung jawab pelanggan"}),
  scopes=G,
  label="Angka penjualan milik",
  help="Sales pada pesanan (dengan pembagian tim) atau sales penanggung jawab pelanggan saat ini.",
  impact="Memindahkan angka antar-sales.",
  example="Pelanggan pindah ke Budi: pesanan lama tetap milik Andi pada Sales pada pesanan",
  consumers=_PEMBACA, risk="high", requires_reason=True, permission=_IZIN)

E("insentif.harga_acuan", group="harga-diskon", section="komisi", type="enum", default="daftar_pt",
  options=({"value": "daftar_pt", "label": "Harga daftar PT"},
           {"value": "umum", "label": "Harga umum"},
           {"value": "batas_bawah", "label": "Batas bawah harga"}),
  scopes=G,
  label="Harga pembanding kualitas harga",
  help="Harga yang dipakai menilai apakah sales menjual di bawah harga.",
  impact="Mengubah persen realisasi harga.",
  example="Jual Rp 50.000, harga daftar Rp 58.000 → realisasi 86,2 %",
  consumers=_PEMBACA, risk="high", requires_reason=True, permission=_IZIN)
