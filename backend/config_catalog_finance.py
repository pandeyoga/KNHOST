"""FASE G-1 — Katalog konfigurasi **AMANDEMEN DOKUMEN**.

Pemilik menegaskan: *“jangan hardcode aturan”*. Karena itu seluruh ambang yang
menentukan kapan sebuah koreksi boleh langsung jalan dan kapan wajib disetujui
didaftarkan di registry — bisa diubah admin dari Pusat Pengaturan tanpa deploy,
lengkap dengan penjelasan awam, contoh angka, dan riwayat perubahan.

Semua kunci di sini dikonsumsi oleh `services/amendment_service.py`.
"""
from config_registry import E

G = ("global", "entity")

# KP-T4 — alasan baku kunci persetujuan yang pindah ke Aturan Persetujuan.
_KPT4_TIDAK_DIPAKAI = ("Dipindah ke Aturan Persetujuan (Pengaturan › Persetujuan › Aturan Persetujuan). Nilai terakhirnya hanya membentuk aturan bawaan selama aturan belum disimpan.")

E("amendment.approval_threshold_amount", group="retur-koreksi", section="koreksi", type="money",
  default=5000000, min=0, max=100000000000, step=1000000, unit="Rp", scopes=G,
  label="Koreksi wajib disetujui mulai (rupiah)",
  help="Bila sebuah koreksi mengubah nilai dokumen sebesar angka ini atau lebih, koreksi tidak langsung jalan; "
       "harus disetujui dulu. Isi 0 = batas rupiah tidak dipakai.",
  impact="Menentukan koreksi mana yang boleh langsung diterapkan pengaju dan mana yang masuk antrean persetujuan.",
  example="Ambang Rp 5.000.000 · koreksi menurunkan tagihan Rp 7.500.000 → WAJIB disetujui",
  consumers=("services/amendment_service.py:policy_snapshot",), risk="high",
  related=("amendment.approval_threshold_pct", "amendment.approver_role"))

E("amendment.approval_threshold_pct", group="retur-koreksi", section="koreksi", type="pct",
  default=5.0, min=0, max=100, step=0.5, unit="%", scopes=G,
  label="Koreksi wajib disetujui mulai (persen)",
  help="Selain batas rupiah, koreksi juga wajib disetujui bila mengubah nilai dokumen lebih dari persen ini. Cukup "
       "salah satu yang terlampaui. Isi 0 = batas persen tidak dipakai.",
  impact="Menjaring koreksi kecil-nilai pada dokumen kecil yang secara persentase besar.",
  example="Ambang 5% · dokumen Rp 20.000.000 turun Rp 2.000.000 (10%) → WAJIB disetujui",
  consumers=("services/amendment_service.py:policy_snapshot",), risk="high",
  related=("amendment.approval_threshold_amount",))

E("amendment.approver_role", group="retur-koreksi", section="koreksi", type="enum", default="manager",
  options=({"value": "manager", "label": "Manajer"},
           {"value": "admin", "label": "Admin / Direksi"}),
  scopes=G,
  label="Siapa yang menyetujui koreksi",
  help="Peran yang menyetujui koreksi biasa. Koreksi bernilai sangat besar tetap naik ke admin.",
  impact="Menentukan antrean persetujuan koreksi masuk ke peran yang mana.",
  example="Manajer → koreksi Rp 7.500.000 menunggu persetujuan Manajer",
  consumers=("services/approval_policy_service.py:default_rows_for",), risk="high",
  # KP-T4 — isi kunci ini pindah ke tabel kebijakan persetujuan (`approval_policies`).
  status="not_used", not_used_reason=_KPT4_TIDAK_DIPAKAI)

E("amendment.admin_approval_above", group="retur-koreksi", section="koreksi", type="money",
  default=50000000, min=0, max=100000000000, step=5000000, unit="Rp", scopes=G,
  label="Koreksi besar wajib disetujui admin mulai",
  help="Di atas angka ini persetujuan Manajer tidak cukup; harus admin/direksi.",
  impact="Menaikkan tingkat persetujuan untuk koreksi bernilai besar.",
  example="Ambang Rp 50.000.000 · koreksi Rp 80.000.000 → hanya admin yang bisa menyetujui",
  consumers=("services/approval_policy_service.py:default_rows_for",), risk="high",
  related=("amendment.approver_role",),
  # KP-T4 — isi kunci ini pindah ke tabel kebijakan persetujuan (`approval_policies`).
  status="not_used", not_used_reason=_KPT4_TIDAK_DIPAKAI)

E("amendment.dual_control", group="retur-koreksi", section="koreksi", type="bool", default=True, scopes=G,
  label="Koreksi: pengaju tak boleh setujui sendiri",
  help="Orang yang mengajukan koreksi tidak boleh menyetujuinya sendiri, walau perannya berwenang.",
  impact="Mencegah satu orang mengubah angka uang sendirian tanpa mata kedua.",
  example="Aktif · Manajer mengajukan koreksi → harus Manajer/admin LAIN yang menyetujui",
  consumers=("services/amendment_service.py:decide",), risk="high",
  # KF-T6 — nilai yang berlaku dipindahkan sekali jalan ke `kontrol.amandemen.min_orang`.
  status="not_used", not_used_reason="Dipindahkan ke Pengaturan › Persetujuan › Kontrol dua orang.")

E("amendment.require_note_above", group="retur-koreksi", section="koreksi", type="money",
  default=10000000, min=0, max=100000000000, step=1000000, unit="Rp", scopes=G,
  label="Koreksi wajib berpenjelasan mulai",
  help="Koreksi senilai angka ini atau lebih harus disertai penjelasan tertulis; memilih label alasan saja tidak "
       "cukup. Isi 0 = penjelasan tertulis tidak diwajibkan.",
  impact="Menolak pengajuan koreksi besar yang tidak menyertakan penjelasan.",
  example="Ambang Rp 10.000.000 · koreksi Rp 12.000.000 tanpa catatan → DITOLAK",
  consumers=("services/amendment_service.py:policy_snapshot",), risk="medium")

E("amendment.issued_doc_policy", group="retur-koreksi", section="koreksi", type="enum", default="note_only",
  options=({"value": "note_only",
            "label": "Hanya lewat Nota Kredit/Debit (dokumen terbit tidak pernah diubah)"},
           {"value": "allow_re_derive",
            "label": "Boleh menghitung ulang dokumen terbit (TIDAK disarankan)"}),
  scopes=G,
  label="Cara mengoreksi dokumen yang sudah terbit",
  help="Dokumen yang sudah terbit sebaiknya tidak diubah angkanya; koreksinya diterbitkan sebagai Nota Kredit "
       "(nilai turun) atau Nota Debit (nilai naik) yang tertaut ke dokumen asal.",
  impact="Menentukan apakah koreksi menghasilkan nota baru atau menimpa dokumen asal.",
  example="Hanya lewat nota · pesanan sudah dibayar lalu harga dikoreksi turun Rp 500.000 → terbit Nota Kredit",
  consumers=("services/amendment_service.py:policy_snapshot",), risk="high")
