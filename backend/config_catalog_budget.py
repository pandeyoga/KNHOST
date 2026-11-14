"""PK-39 (FY-12, keputusan K-12) — Katalog konfigurasi **ANGGARAN**.

Mode pemeriksaan anggaran dulu disimpan di koleksi `fin_budget_rules` (di luar Pusat Pengaturan) dan hanya dipakai
saat PO dibuat/disetujui. Kini satu kunci berlapis global → PT yang dibaca `services/budget_service.py:get_rules`
untuk semua titik pemeriksaan: PO dibuat & disetujui, tagihan tanpa PO disetujui, kas keluar dicatat, LPJ diajukan
dan disetujui. Nilai `fin_budget_rules.mode` lama PT itu tetap dipakai sampai lapisan PT kunci ini diisi (penimpa
`mode_anggaran_lama` di `services/config_overrides.py`; tidak ada penulisan data saat pemasangan).
"""
from config_registry import E

G = ("global", "entity")

# ASUMSI unit: pilihan "mati" dipertahankan walau K-12 hanya menyebut peringatan dan blokir (mode `off` ada hari ini).
E("budget.mode", group="keuangan-dasar", type="enum", default="peringatan",
  options=({"value": "mati", "label": "Mati"},
           {"value": "peringatan", "label": "Peringatkan"},
           {"value": "blokir", "label": "Tolak bila melampaui"}),
  scopes=G,
  label="Bila belanja melampaui anggaran",
  help="Berlaku saat membuat dan menyetujui PO, menyetujui tagihan tanpa PO, mencatat kas keluar, dan menyetujui "
       "LPJ. Peringatkan = transaksi tetap jalan dengan catatan; Tolak = transaksi ditahan sampai pagu dinaikkan.",
  impact="Tolak dapat menghentikan pembelian dan pengeluaran harian bila pagu belum diisi lengkap.",
  example="Peringatkan · pagu sewa bulan ini Rp 1.000.000, terpakai Rp 900.000, kas keluar Rp 200.000 → tersimpan "
          "dengan peringatan lebih Rp 100.000",
  consumers=("services/budget_service.py:get_rules",),
  risk="high", requires_reason=True,
  permission=("budget", "configure"))
