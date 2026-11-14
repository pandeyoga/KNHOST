"""PS-20 (D-14) — Katalog konfigurasi **PENEGAKAN MATRIKS PERSETUJUAN DIVISI**.

Semua sakelar di sini muncul otomatis di **Pusat Pengaturan → "Persetujuan & Ambang"**
(UI di-generate dari registry FASE G-0), sehingga pemilik dapat mengubah kebijakan
tanpa deploy — termasuk keputusan pemilik D-14: apakah penegakan berlaku untuk
dokumen yang MASIH MENUNGGU persetujuan (bawaan) atau hanya dokumen baru.

Konsumen nyata: `services/approval_matrix_service.py` (dipakai routers/rnd.py,
routers/purchase_requisitions.py, routers/special_orders.py, routers/approvals_matrix.py).
"""
from config_registry import E

G = ("global", "entity")
_SVC = "services/approval_matrix_service.py"

# KP-T4 — alasan baku kunci persetujuan yang pindah ke Aturan Persetujuan.
_KPT4_TIDAK_DIPAKAI = ("Dipindah ke Aturan Persetujuan (Pengaturan › Persetujuan › Aturan Persetujuan). Nilai terakhirnya hanya membentuk aturan bawaan selama aturan belum disimpan.")

E("approval.matrix_enforcement", group="persetujuan", section="rnd", type="enum", default="enforce",
  options=({"value": "off", "label": "Nonaktif — matriks hanya jadi rujukan tampilan"},
           {"value": "warn", "label": "Peringatkan saja — dicatat, tetapi tetap boleh lanjut"},
           {"value": "enforce", "label": "Tegakkan — tolak bila bukan penyetuju yang berhak"}),
  scopes=G,
  label="Aturan persetujuan R&D: seberapa tegas",
  help="Menentukan apakah daftar “siapa berhak menyetujui” di R&D (desain, sample, pesanan khusus, permintaan "
       "pembelian) benar-benar ditegakkan, hanya memberi peringatan, atau sekadar rujukan.",
  impact="Pada 'Tegakkan', percobaan menyetujui oleh peran yang tidak berhak (atau oleh "
         "pengaju dokumen itu sendiri) akan DITOLAK dengan pesan jelas dan tercatat di "
         "jejak persetujuan. Pada 'Peringatkan saja', tindakan tetap lanjut namun ditandai "
         "pelanggaran di jejak sehingga bisa diaudit.",
  example="Sales mencoba meng-ACC desain → ditolak: hanya Manajer (atau Direksi/Admin) yang berhak",
  consumers=("services/approval_policy_service.py:default_rows_for",),
  related=("approval.matrix_scope", "approval.matrix_sod"), risk="high",
  permission=("rnd", "manage"),
  # KP-T4 — isi kunci ini pindah ke tabel kebijakan persetujuan (`approval_policies`).
  status="not_used", not_used_reason=_KPT4_TIDAK_DIPAKAI)

E("approval.matrix_scope", group="persetujuan", section="rnd", type="enum", default="all_pending",
  options=({"value": "all_pending", "label": "Semua dokumen — termasuk yang masih menunggu persetujuan"},
           {"value": "new_only", "label": "Hanya dokumen baru — dokumen lama memakai cara lama"}),
  scopes=G,
  label="Aturan R&D baru berlaku untuk dokumen mana",
  help="Saat aturan persetujuan R&D diperketat, pilih apakah dokumen yang sudah mengantre ikut aturan baru atau "
       "diselesaikan dengan cara lama.",
  impact="Pada 'Hanya dokumen baru', dokumen yang dibuat SEBELUM tanggal berlaku di bawah tidak diperiksa matriks "
         "(tetap bisa diselesaikan penyetuju lama).",
  example="Ada 5 PR menunggu sejak minggu lalu → pada 'Semua dokumen', kelimanya kini wajib disetujui Manajer yang "
          "bukan pengajunya",
  consumers=("services/approval_policy_service.py:default_rows_for",),
  related=("approval.matrix_effective_from",), risk="high",
  permission=("rnd", "manage"),
  # KP-T4 — isi kunci ini pindah ke tabel kebijakan persetujuan (`approval_policies`).
  status="not_used", not_used_reason=_KPT4_TIDAK_DIPAKAI)

E("approval.matrix_effective_from", group="persetujuan", section="rnd", type="text", default="",
  scopes=G,
  label="Tanggal mulai aturan persetujuan R&D",
  help="Dipakai bila memilih “Hanya dokumen baru”: dokumen sebelum tanggal ini memakai cara lama. Kosong berarti "
       "hari ini.",
  impact="Mengubah tanggal ini menggeser garis batas antara dokumen lama dan baru.",
  example="Diisi 2026-08-10 → PR tanggal 9 Agustus tidak diperiksa, PR tanggal 10 Agustus diperiksa",
  consumers=("services/approval_policy_service.py:default_rows_for",),
  related=("approval.matrix_scope",), risk="medium",
  permission=("rnd", "manage"),
  # KP-T4 — isi kunci ini pindah ke tabel kebijakan persetujuan (`approval_policies`).
  status="not_used", not_used_reason=_KPT4_TIDAK_DIPAKAI,
  value_format="date")

E("approval.matrix_sod", group="persetujuan", section="rnd", type="bool", default=True, scopes=G,
  label="R&D: pengaju tak boleh setujui sendiri",
  help="Orang yang mengajukan dokumen R&D tidak bisa menyetujui dokumennya sendiri, walau perannya berwenang.",
  impact="Pada posisi aktif, Manajer yang mengajukan PR-nya sendiri harus meminta Manajer lain atau Direksi/Admin "
         "untuk menyetujui.",
  example="Manajer Dewi mengajukan PR bahan sample → Dewi tidak bisa menyetujuinya sendiri",
  consumers=(f"{_SVC}:evaluate", f"{_SVC}:is_requester"),
  related=("approval.matrix_enforcement",), risk="high",
  permission=("rnd", "manage"),
  # KF-T6 — nilai yang berlaku dipindahkan sekali jalan (`dual_control.migrasi_sakelar_lama`) ke kontrol.*.min_orang.
  status="not_used", not_used_reason="Dipindahkan ke Pengaturan › Persetujuan › Kontrol dua orang.")

E("approval.po_custom_direksi_min", group="persetujuan", section="rnd", type="money", default=50000000,
  min=0, step=1000000, unit="Rp", scopes=G,
  label="Pesanan khusus naik ke Direksi mulai",
  help="Pesanan khusus selalu disetujui Manajer lebih dulu; bila nilainya mencapai angka ini, perlu persetujuan "
       "kedua dari Direksi.",
  impact="Menaikkan angka membuat lebih banyak pesanan cukup disetujui Manajer saja; menurunkannya membuat lebih "
         "banyak pesanan wajib menunggu Direksi.",
  example="Diisi 50.000.000 → pesanan khusus Rp 80 juta butuh Manajer LALU Direksi",
  consumers=("services/approval_policy_service.py:default_rows_for",),
  related=("approval.matrix_enforcement",), risk="medium",
  permission=("rnd", "manage"),
  # KP-T4 — isi kunci ini pindah ke tabel kebijakan persetujuan (`approval_policies`).
  status="not_used", not_used_reason=_KPT4_TIDAK_DIPAKAI)
