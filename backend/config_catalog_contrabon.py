"""FASE G-7 — Katalog konfigurasi **KONTRABON** (siklus tukar faktur supplier).

Kenapa ini config dan bukan angka di dalam kode: pemilik usaha yang menentukan berapa
selisih 3-way match yang masih boleh lewat tanpa sengketa, nominal berapa yang wajib
disetujui admin, dan kapan pengingat tukar faktur dikirim. Keputusan pemilik 2026-07-30:
*"toleransi 3-way match jadikan config"* + *"jadwal tukar faktur perlu pengingat"*.

Semua kunci di sini dikonsumsi `services/contra_bon_service.py` dan
`services/contra_bon_reminder.py`.

CATATAN DESAIN TOLERANSI (dua knob, sengaja):
  Satu selisih dianggap **pengecualian** hanya bila MELEWATI KEDUANYA — persentase DAN
  nilai rupiah. Alasannya nyata: selisih 0,4 meter pada 20 meter = 2% (di atas ambang
  persen) tetapi nilainya cuma belasan ribu rupiah; kalau itu dijadikan pengecualian,
  petugas harus mengetik alasan untuk uang receh dan akhirnya memilih alasan sembarang.
  Sebaliknya selisih Rp 2.000.000 pada tagihan Rp 500.000.000 = 0,4% (di bawah persen)
  tapi nominalnya besar — ambang rupiah yang menangkapnya.
"""
from config_registry import E

G = ("global", "entity")

# KP-T4 — alasan baku kunci persetujuan yang pindah ke Aturan Persetujuan.
_KPT4_TIDAK_DIPAKAI = ("Dipindah ke Aturan Persetujuan (Pengaturan › Persetujuan › Aturan Persetujuan). Nilai terakhirnya hanya membentuk aturan bawaan selama aturan belum disimpan.")

# KF-T2 (L5) — sejak KN-D16 persen 3-way dibaca dari `purchasing.bill_qty_tolerance_percent`; kunci ini tidak dibaca
# mesin lagi, jadi ditandai tidak dipakai (bukan label "(Lama)" pada kunci yang tampil seolah aktif).
E("contra_bon.qty_tolerance_percent", group="pembelian", section="tagihan", type="pct", default=1.0,
  min=0, max=100, step=0.5, unit="%", scopes=G,
  label="Toleransi persen kontrabon",
  help="Tidak dipakai lagi. Toleransi persen sekarang satu untuk tagihan pemasok dan kontrabon: “Toleransi jumlah "
       "di tagihan pemasok” dan “Toleransi harga tagihan pemasok”.",
  impact="Tidak berpengaruh lagi.",
  example="Toleransi 1% · diterima 1.000 yard, ditagih 1.020 yard (+2%) senilai Rp 400.000 "
          "→ melewati keduanya → wajib keputusan berlabel",
  consumers=("services/contra_bon_service.py:tolerances",), risk="medium",
  related=("contra_bon.value_tolerance_rupiah", "contra_bon.require_reason_out_of_tolerance"),
  status="not_used",
  not_used_reason="Toleransi jumlah kontrabon mengikuti pengaturan 'Toleransi jumlah tagihan pemasok'.")

E("contra_bon.value_tolerance_rupiah", group="pembelian", section="tagihan", type="money", default=50000,
  min=0, step=10000, unit="Rp", scopes=G,
  label="Selisih kecil kontrabon yang diabaikan",
  help="Selisih yang nilainya di bawah angka ini diabaikan walau persennya besar, supaya petugas tidak perlu "
       "menulis alasan untuk uang receh. Isi 0 = tidak ada selisih yang diabaikan karena kecil.",
  impact="Menyaring pengecualian bernilai kecil agar antrean keputusan tetap bermakna.",
  example="Ambang Rp 50.000 · selisih 0,4 meter senilai Rp 18.000 → diabaikan (lolos)",
  consumers=("services/three_way_policy.py:tolerances",
             "services/contra_bon_service.py:policy"), risk="medium",
  related=("contra_bon.qty_tolerance_percent",))

E("contra_bon.require_reason_out_of_tolerance", group="pembelian", section="tagihan", type="bool", default=True,
  scopes=G,
  label="Selisih kontrabon wajib diputus dulu",
  help="Kontrabon tidak bisa diverifikasi selama masih ada selisih di luar toleransi yang belum diputuskan (terima, "
       "potong, atau sengketakan) beserta alasannya.",
  impact="Mencegah selisih diterima diam-diam.",
  example="Aktif · ada 1 selisih belum diputus → tombol Verifikasi ditolak dengan penjelasan",
  consumers=("services/contra_bon_service.py:policy",), risk="high")

E("contra_bon.approval_threshold_rupiah", group="pembelian", section="tagihan", type="money", default=50000000,
  min=0, step=1000000, unit="Rp", scopes=G,
  label="Kontrabon bernilai besar mulai",
  help="Kontrabon dengan nilai bersih di atas angka ini harus disetujui peran yang lebih tinggi.",
  impact="Menentukan kapan pembayaran borongan ke pemasok harus naik ke admin.",
  example="Ambang Rp 50.000.000 · kontrabon Rp 120.000.000 → wajib disetujui admin",
  consumers=("services/approval_policy_service.py:default_rows_for",), risk="high",
  related=("contra_bon.approval_role", "contra_bon.high_value_approval_role"),
  # KP-T4 — isi kunci ini pindah ke tabel kebijakan persetujuan (`approval_policies`).
  status="not_used", not_used_reason=_KPT4_TIDAK_DIPAKAI)

E("contra_bon.approval_role", group="pembelian", section="tagihan", type="enum", default="manager", scopes=G,
  options=[{"value": "manager", "label": "Manajer"}, {"value": "admin", "label": "Admin"}],
  label="Peran penyetuju kontrabon",
  help="Peran minimal yang boleh menyetujui kontrabon bernilai di bawah ambang.",
  impact="Menentukan siapa yang boleh melepas pembayaran borongan ke pemasok.",
  example="Manajer · kontrabon Rp 20.000.000 bisa disetujui Manajer",
  consumers=("services/approval_policy_service.py:default_rows_for",), risk="high",
  # KP-T4 — isi kunci ini pindah ke tabel kebijakan persetujuan (`approval_policies`).
  status="not_used", not_used_reason=_KPT4_TIDAK_DIPAKAI)

E("contra_bon.high_value_approval_role", group="pembelian", section="tagihan", type="enum", default="admin",
  scopes=G,
  options=[{"value": "manager", "label": "Manajer"}, {"value": "admin", "label": "Admin"}],
  label="Peran penyetuju kontrabon bernilai besar",
  help="Peran minimal untuk kontrabon di atas 'Ambang kontrabon bernilai besar'.",
  impact="Uang besar tidak boleh dilepas oleh wewenang yang sama dengan uang kecil.",
  example="Admin · kontrabon Rp 120.000.000 ditolak bila disetujui Manajer",
  consumers=("services/approval_policy_service.py:default_rows_for",), risk="high",
  # KP-T4 — isi kunci ini pindah ke tabel kebijakan persetujuan (`approval_policies`).
  status="not_used", not_used_reason=_KPT4_TIDAK_DIPAKAI)

E("contra_bon.reminder_days_before", group="pembelian", section="tagihan", type="int", default=1,
  min=0, max=14, step=1, unit="hari", scopes=G,
  label="Pengingat tukar faktur: berapa hari sebelum",
  help="Berapa hari sebelum jadwal tukar faktur pemasok pengingat dikirim, berisi penerimaan barang yang belum "
       "ditagih dan tagihan yang siap dikontrabon. Isi 0 = pengingat dikirim pada hari jadwal itu sendiri.",
  impact="Mencegah siklus tukar faktur terlewat dan faktur pemasok menumpuk tanpa dibayar.",
  example="H-1 · jadwal Selasa → pengingat terkirim Senin pagi",
  consumers=("services/contra_bon_service.py:policy",), risk="low",
  related=("contra_bon.unbilled_gr_age_days",))

E("contra_bon.unbilled_gr_age_days", group="pembelian", section="tagihan", type="int", default=3,
  min=0, max=90, step=1, unit="hari", scopes=G,
  label="Barang diterima belum ditagih: batas hari",
  help="Penerimaan barang yang sudah lewat sekian hari tetapi belum ditagih pemasok ditandai tertunggak dan ikut "
       "disebut di pengingat. Isi 0 = penerimaan yang belum ditagih langsung ditandai tertunggak keesokan harinya.",
  impact="Membuat barang yang sudah masuk gudang tetapi belum ada fakturnya kelihatan.",
  example="Batas 3 hari · GR 5 hari lalu belum ditagih → ditandai tertunggak",
  consumers=("services/contra_bon_service.py:policy",), risk="low")

E("contra_bon.verify_sla_days", group="pembelian", section="tagihan", type="int", default=2,
  min=1, max=60, step=1, unit="hari", scopes=G,
  label="Batas waktu verifikasi kontrabon (hari)",
  help="Berapa hari kontrabon boleh menunggu diverifikasi atau disetujui sebelum ditandai terlambat dan dinaikkan "
       "ke atasan.",
  impact="Pemasok tidak menunggu tanpa kejelasan; antrean kontrabon jadi disiplin.",
  example="SLA 2 hari · kontrabon disubmit 3 hari lalu belum diverifikasi → TERLAMBAT",
  consumers=("services/contra_bon_service.py:policy",), risk="low")

E("contra_bon.block_pay_before_approval", group="pembelian", section="tagihan", type="bool", default=True,
  scopes=G,
  label="Larang pembayaran sebelum kontrabon disetujui",
  help="Bila aktif, kontrabon hanya bisa dibayar setelah status 'Disetujui' atau "
       "'Dijadwalkan bayar'. Bila dimatikan, kontrabon terverifikasi boleh langsung dibayar "
       "(dipakai perusahaan kecil yang pemiliknya sendiri yang membayar).",
  impact="Menentukan apakah persetujuan adalah gerbang wajib sebelum uang keluar.",
  example="Aktif · kontrabon berstatus Terverifikasi ditolak saat dibayar dengan penjelasan",
  consumers=("services/contra_bon_service.py:policy",), risk="high")
