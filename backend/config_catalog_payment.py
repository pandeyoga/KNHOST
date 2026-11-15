"""FASE G-2 — Katalog konfigurasi **RENCANA PEMBAYARAN & DENDA**.

Pemilik menegaskan sejak FASE G: *"jangan hardcode aturan"*. Cara cicilan dibentuk
dan cara denda diperlakukan adalah keputusan BISNIS yang berubah-ubah, jadi seluruhnya
didaftarkan di registry dan bisa diubah admin dari **Pusat Pengaturan → Uang Masuk &
Piutang** tanpa deploy.

Catatan penting (satu sumber kebenaran):
  * **bunga denda** memakai kunci yang SUDAH ADA `ar.denda_rate_pct_per_month`;
  * **masa tenggang** memakai `ar.grace_days`.
  Keduanya sengaja TIDAK diduplikasi di sini supaya laporan Umur Piutang dan nota denda
  tidak pernah bercerita beda. Kunci di bawah hanya untuk hal yang benar-benar BARU.

Setiap kunci WAJIB punya pembaca nyata di `services/` (gate `audit_config_wiring.py` +
INV-CFG-01 akan memerah bila tidak).
"""
from config_registry import E

G = ("global", "entity")
GC = ("global", "entity", "customer")
# KF-T5 — kunci ber-`GC` bisa dibedakan per pelanggan dari kartu pelanggan (Customer360Panel › Aturan khusus pelanggan
# ini); `help`-nya diakhiri kalimat "Bisa dibedakan per pelanggan dari kartu pelanggan."

# ── Rencana pembayaran ──────────────────────────────────────────────────────
# KP-T4 — alasan baku kunci persetujuan yang pindah ke Aturan Persetujuan.
_KPT4_TIDAK_DIPAKAI = ("Dipindah ke Aturan Persetujuan (Pengaturan › Persetujuan › Aturan Persetujuan). Nilai terakhirnya hanya membentuk aturan bawaan selama aturan belum disimpan.")

E("payment.plan_required_above_amount", group="pembayaran-pelanggan", section="syarat-bayar", type="money", default=0,
  min=0, max=100000000000, step=1000000, unit="Rp", scopes=G,
  label="Pesanan besar wajib punya jadwal bayar",
  help="Pesanan bernilai di atas angka ini harus punya rencana pembayaran (DP atau cicilan), tidak cukup tempo "
       "biasa. Isi 0 bila tidak ingin mewajibkan.",
  impact="Menentukan kapan sistem mengingatkan bahwa pesanan besar belum punya jadwal bayar.",
  example="Rp 50.000.000 · SO Rp 80.000.000 tanpa rencana → ditandai perlu rencana pembayaran",
  consumers=("services/payment_plan_service.py:plan_policy",), risk="medium",
  related=("payment.plan_tolerance_rupiah",))

E("payment.plan_tolerance_rupiah", group="pembayaran-pelanggan", section="syarat-bayar", type="money", default=1,
  min=1, max=100000, step=1, unit="Rp", scopes=G,   # KF-T3 (KF-10) — 0 dulu diganti diam-diam menjadi 1
  label="Toleransi pembulatan rencana pembayaran",
  help="Selisih rupiah yang masih diterima antara jumlah semua cicilan dan nilai pesanan, karena persen sering "
       "menghasilkan pecahan rupiah. Paling kecil Rp 1.",
  impact="Terlalu besar membuat rencana yang tidak pas ikut lolos; terlalu kecil membuat "
         "pembulatan persen ditolak terus.",
  example="Toleransi Rp 1 · jumlah cicilan Rp 9.999.999 untuk pesanan Rp 10.000.000 → diterima; selisih Rp 2 → "
          "ditolak",
  consumers=("services/payment_plan_service.py:plan_policy",), risk="high",
  related=("payment.plan_required_above_amount",))

E("payment.default_dp_percent", group="pembayaran-pelanggan", section="syarat-bayar", type="pct", default=30.0,
  min=0, max=100, step=5, unit="%", scopes=G,
  label="Uang muka (DP) bawaan",
  help="Persen DP yang dipakai saat rencana pembayaran dibuat dari template DP + cicilan. Tetap bisa diubah bebas "
       "per pesanan. Isi 0 = jadwal dari templat dimulai tanpa DP.",
  impact="Mengubah angka awal pada pembuat rencana pembayaran.",
  example="30% · order Rp 20.000.000 → DP Rp 6.000.000",
  consumers=("services/payment_plan_service.py:plan_policy",), risk="low",
  related=("payment.default_installments",))

E("payment.default_installments", group="pembayaran-pelanggan", section="syarat-bayar", type="int", default=3,
  min=1, max=36, step=1, unit="kali", scopes=G,
  label="Jumlah cicilan bawaan",
  help="Berapa kali sisa setelah DP dipecah saat memakai template DP + cicilan.",
  impact="Mengubah jumlah baris cicilan yang dihasilkan template.",
  example="3 kali · sisa Rp 14.000.000 → 3 baris Rp 4.666.667 (pembulatan di baris terakhir)",
  consumers=("services/payment_plan_service.py:plan_policy",), risk="low",
  related=("payment.default_installment_interval",))

E("payment.default_installment_interval", group="pembayaran-pelanggan", section="syarat-bayar", type="enum", default="monthly",
  options=({"value": "monthly", "label": "Bulanan"}, {"value": "weekly", "label": "Mingguan"}),
  scopes=G,
  label="Jarak antar cicilan bawaan",
  help="Jatuh tempo cicilan berikutnya dihitung bulanan atau mingguan dari cicilan sebelumnya.",
  impact="Mengubah tanggal jatuh tempo yang dihasilkan template.",
  example="Bulanan · DP 1 Juli → cicilan 1 Agt, 1 Sep, 1 Okt",
  consumers=("services/payment_plan_service.py:plan_policy",), risk="low",
  related=("payment.default_installments",))

# ── PM-T2 — cara bayar & rekening tujuan di pesanan, kode bayar ─────────────
# Kelompok "uang-masuk" (alias kelompok ini). Diubah pemegang izin kelola rekening (`cash.configure`), seperti daftar
# Cara Bayar dan rekening penerimaan (PM-T1).
E("payment.wajib_cara_bayar_di_pesanan", group="uang-masuk", section="syarat-bayar", type="bool", default=False,
  scopes=G, permission=("cash", "configure"),
  sensitif_baca=False,   # dibaca layar checkout semua sales (pilihan "Belum ditentukan" disembunyikan bila menyala)
  label="Wajibkan cara bayar saat membuat pesanan",
  help="Bila menyala, pesanan tidak bisa dibuat tanpa memilih cara bayar.",
  impact="Sales harus memilih cara bayar di checkout; aplikasi lama yang tidak mengirimnya akan ditolak.",
  example="Menyala · checkout tanpa cara bayar → ditolak",
  consumers=("routers/sales_orders.py:create_order",), risk="medium",
  related=("payment.kode_bayar_awalan",))

E("payment.kode_bayar_awalan", group="uang-masuk", section="syarat-bayar", type="text", default="KN",
  scopes=("global",), permission=("cash", "configure"), value_format="kode_huruf",   # kode unik lintas PT
  label="Awalan kode bayar",
  help="Huruf di depan kode bayar yang ditulis pelanggan di berita transfer. Dua sampai empat huruf besar.",
  impact="Hanya kode baru yang memakai awalan baru; kode lama tetap berlaku.",
  example="KN → KN-7F3K2",
  consumers=("services/payment_code_service.py:ensure_for_order", "services/payment_code_service.py:ensure_for_line"),
  risk="low", related=("payment.wajib_cara_bayar_di_pesanan",))

# ── PM-T3 — kwitansi ber-rekening & ber-referensi; status "terverifikasi bank" ────────────────────────────────────
# Diubah pemegang izin kelola rekening (`cash.configure`), sama dengan kunci PM-T2. Label dipendekkan dari spesifikasi
# (batas 45 huruf INV-CFG-TXT) — usulan koreksi teks di laporan unit.
E("payment.wajib_nomor_referensi", group="uang-masuk", section="kwitansi", type="bool", default=False,
  scopes=G, permission=("cash", "configure"),
  sensitif_baca=False,   # dibaca form kwitansi semua pemegang akses mencatat pembayaran (tanda wajib di isian)
  label="Wajibkan nomor referensi di kwitansi",
  help="Berlaku untuk cara bayar yang butuh referensi (transfer, giro, QRIS).",
  impact="Menyala = kwitansi transfer tanpa nomor referensi ditolak.",
  example="Menyala · transfer tanpa referensi → ditolak",
  consumers=("services/ar_receipt_service.py:periksa_uang_masuk",), risk="medium",
  related=("payment.hari_wajar_verifikasi_bank",))

E("payment.hari_wajar_verifikasi_bank", group="bank", section="kwitansi-bank", type="int", default=3,
  min=0, max=60, step=1, unit="hari", scopes=G, permission=("cash", "configure"),
  sensitif_baca=False,   # dibaca layar Riwayat Pembayaran (judul saringan "Belum terverifikasi lebih dari N hari")
  label="Kwitansi wajar belum terverifikasi (hari)",
  help="Kwitansi non-tunai yang lebih lama dari ini tampil di daftar 'Belum terverifikasi'. 0 = semua kwitansi "
       "non-tunai yang belum cocok dengan mutasi bank langsung tampil.",
  impact="Hanya mengubah isi daftar; tidak menolak apa pun.",
  example="3 · kwitansi berumur 5 hari → tampil",
  consumers=("services/ar_receipt_service.py:saringan_verifikasi",), risk="low",
  related=("payment.wajib_nomor_referensi",))

E("finance.tahan_kirim_dasar_bayar", group="uang-masuk", section="syarat-bayar", type="enum", default="tercatat",
  options=({"value": "tercatat", "label": "Tercatat (cukup ada kwitansi)"},
           {"value": "terverifikasi", "label": "Terverifikasi bank (cocok dengan mutasi)"}),
  scopes=G, permission=("cash", "configure"), requires_reason=True,
  label="Bayar-dulu boleh dikirim setelah pembayaran",
  help="'Tercatat' = cukup ada kwitansi. 'Terverifikasi' = kwitansi harus sudah cocok dengan mutasi bank. "
       "Kwitansi tunai yang masuk rekening kas selalu dihitung.",
  impact="'Terverifikasi' menahan barang sampai mutasi bank dicocokkan.",
  example="Terverifikasi · CBD dibayar, mutasi belum cocok → tertahan",
  # Dibaca `_basis` (dipanggil `evaluate` untuk tiap pesanan yang ditahan termin bayar-dulu).
  consumers=("services/dispatch_payment_gate.py:_basis",), risk="high",
  related=("finance.dispatch_payment_gate",))

# ── PM-T4 — tunai yang diterima sales dicatat sebagai titipan sampai disetor (K-36) ───────────────────────────────
# Awalan `pembayaran.` menyimpang dari `02` §2.1 (domain yang ada `payment`) karena K-36 menyebut nama kunci ini.
# Diubah pemegang izin kelola rekening (`cash.configure`), sama dengan kunci PM-T2/PM-T3. Bawaan `kas_langsung` =
# perilaku hari ini (titik henti H5: mengubahnya untuk PT nyata = keputusan pemilik).
E("pembayaran.sales_terima_tunai", group="uang-masuk", section="kwitansi", type="enum", default="kas_langsung",
  options=({"value": "kas_langsung", "label": "Kas langsung (seperti sekarang)"},
           {"value": "titipan", "label": "Titipan di tangan sales sampai disetor"},
           {"value": "dilarang", "label": "Dilarang (sales tidak bisa mencatat tunai)"}),
  scopes=G, permission=("cash", "configure"), requires_reason=True,
  sensitif_baca=False,   # dibaca form kwitansi & kartu "Titipan Saya" di HP sales (teks bantu tunai)
  label="Tunai yang diterima sales dicatat sebagai",
  help="'Kas langsung' = seperti sekarang. 'Titipan' = uang dianggap masih di tangan sales sampai disetor. "
       "'Dilarang' = sales tidak bisa mencatat tunai.",
  impact="'Titipan' membuat kas kantor tidak bertambah sampai setoran diterima.",
  example="Titipan · sales terima Rp 300.000 → kas tetap, titipan Rp 300.000",
  consumers=("services/cash_holding_service.py:mode_tunai",), risk="high",
  related=("pembayaran.titipan_batas_nominal", "pembayaran.titipan_tenggat_setor_hari"))

E("pembayaran.titipan_batas_nominal", group="uang-masuk", section="kwitansi", type="money", default=0,
  min=0, max=1_000_000_000, step=100_000, unit="Rp", scopes=G, permission=("cash", "configure"),
  sensitif_baca=False,   # kartu "Titipan Saya" menampilkan batasnya
  label="Batas tunai yang boleh dipegang satu sales",
  help="Jumlah titipan belum disetor per orang. 0 = tanpa batas.",
  impact="Sales yang mencapai batas tidak bisa menerima tunai lagi sebelum menyetor.",
  example="Rp 5.000.000 · sudah pegang Rp 4,8 jt, terima Rp 300 rb → ditolak",
  consumers=("services/cash_holding_service.py:periksa_batas", "services/cash_holding_service.py:ringkasan_saya"),
  risk="medium", related=("pembayaran.sales_terima_tunai",))

E("pembayaran.titipan_tenggat_setor_hari", group="uang-masuk", section="kwitansi", type="int", default=0,
  min=0, max=30, step=1, unit="hari", scopes=G, permission=("cash", "configure"),
  sensitif_baca=False,   # kartu "Titipan Saya" & tab Titipan Sales menandai titipan lewat tenggat
  label="Tunai harus disetor dalam (hari)",
  help="Titipan lebih lama dari ini bertanda lewat tenggat. 0 = tanpa tenggat.",
  impact="Hanya menandai; tidak menolak apa pun.",
  example="1 · diterima Senin, belum disetor Rabu → lewat tenggat",
  consumers=("services/cash_holding_service.py:tenggat_hari",), risk="low",
  related=("pembayaran.sales_terima_tunai",))

# ── Denda keterlambatan sebagai DOKUMEN ────────────────────────────────────
E("payment.penalty_mode", group="pembayaran-pelanggan", section="denda", type="enum", default="draft",
  options=({"value": "off", "label": "Mati (tidak ada denda)"},
           {"value": "draft", "label": "Usulan denda (draf, tanpa jurnal)"},
           {"value": "auto", "label": "Otomatis terbit (langsung berjurnal)"}),
  scopes=GC,
  label="Denda telat: usulan atau langsung terbit",
  help="Usulan: denda dibuat sebagai konsep yang masih bisa dinegosiasikan atau dibatalkan dan belum masuk "
       "pembukuan. Otomatis terbit: denda langsung dicatat sebagai piutang dan pendapatan denda. Bisa dibedakan per "
       "pelanggan dari kartu pelanggan.",
  impact="Menentukan apakah denda hasil pemindaian harian berjurnal atau tidak.",
  example="Usulan · cicilan telat 12 hari → nota denda DRAFT Rp 80.000 menunggu keputusan",
  consumers=("services/penalty_service.py:penalty_policy",), risk="high",
  related=("ar.denda_rate_pct_per_month", "ar.grace_days", "payment.penalty_base"))

E("payment.penalty_base", group="pembayaran-pelanggan", section="denda", type="enum", default="installment",
  options=({"value": "installment", "label": "Nilai cicilan yang telat"},
           {"value": "outstanding", "label": "Seluruh sisa piutang pesanan"}),
  scopes=GC,
  label="Dasar perhitungan denda",
  help="Denda dihitung dari nominal baris cicilan yang telat, atau dari seluruh sisa piutang "
       "pesanan itu. Basis cicilan lebih adil bagi pelanggan yang sudah bayar sebagian."
       " Bisa dibedakan per pelanggan dari kartu pelanggan.",
  impact="Mengubah besar denda pada nota yang terbentuk.",
  example="Basis cicilan · cicilan Rp 5.000.000 telat 30 hari · 2%/bulan → denda Rp 100.000",
  consumers=("services/penalty_service.py:penalty_policy",), risk="high",
  related=("payment.penalty_mode", "payment.penalty_cap_pct"))

E("payment.penalty_cap_pct", group="pembayaran-pelanggan", section="denda", type="pct", default=0.0,
  min=0, max=100, step=1, unit="% dari dasar", scopes=GC,
  label="Batas maksimum denda",
  help="Batas atas denda sebagai persen dari dasar perhitungan. Isi 0 untuk tanpa batas."
       " Bisa dibedakan per pelanggan dari kartu pelanggan.",
  impact="Melindungi hubungan dagang: denda tidak membengkak tanpa batas pada tunggakan lama.",
  example="Batas 10% · dasar Rp 5.000.000 → denda tidak akan melebihi Rp 500.000",
  consumers=("services/penalty_service.py:penalty_policy",), risk="medium",
  related=("payment.penalty_base",))

E("payment.penalty_min_amount", group="pembayaran-pelanggan", section="denda", type="money", default=10000,
  min=0, max=100000000, step=1000, unit="Rp", scopes=G,
  label="Denda minimum yang layak diterbitkan",
  help="Denda di bawah nilai ini tidak dibuatkan nota — biaya administrasinya lebih besar daripada nilainya. Isi 0 "
       "= semua denda dibuatkan nota.",
  impact="Mencegah antrean penuh nota denda receh.",
  example="Rp 10.000 · hasil hitung Rp 4.500 → tidak dibuatkan nota",
  consumers=("services/penalty_service.py:penalty_policy",), risk="low")

E("payment.penalty_waive_requires_approval", group="pembayaran-pelanggan", section="denda", type="bool", default=True,
  scopes=G,
  label="Pembebasan / perubahan denda wajib disetujui",
  help="Bila aktif, membebaskan denda atau mengubah nominalnya wajib melewati persetujuan "
       "(selain wajib memilih label alasan). Ini yang mencegah denda hilang diam-diam.",
  impact="Menentukan apakah pembebasan denda langsung berlaku atau menunggu penyetuju.",
  example="Aktif · sales membebaskan denda Rp 250.000 → menunggu persetujuan Manajer",
  consumers=("services/penalty_service.py:penalty_policy",), risk="high",
  related=("payment.penalty_waive_approver_role",))

E("payment.penalty_waive_approver_role", group="pembayaran-pelanggan", section="denda", type="enum", default="manager",
  options=({"value": "manager", "label": "Manajer"}, {"value": "admin", "label": "Admin / Direksi"}),
  scopes=G,
  label="Siapa yang menyetujui pembebasan denda",
  help="Peran yang berwenang menyetujui pembebasan atau perubahan nominal denda.",
  impact="Menentukan tujuan antrean persetujuan denda.",
  example="Manajer · pembebasan denda masuk Inbox Persetujuan Manajer",
  consumers=("services/penalty_service.py:penalty_policy",), risk="medium",
  related=("payment.penalty_waive_requires_approval",))

# ── FASE G-3 — Selisih pembayaran (lebih / kurang bayar) ───────────────────
# Prinsip: sistem TIDAK menuntut nominal persis, tapi setiap selisih WAJIB punya
# label keputusan. Kunci di bawah menentukan kapan selisih boleh diselesaikan
# otomatis, apa pilihan bawaannya, dan siapa yang boleh menghapus/mengembalikan uang.
E("payment.variance_tolerance_rupiah", group="pembayaran-pelanggan", section="selisih-bayar", type="money", default=5000,
  min=0, max=10000000, step=1000, unit="Rp", scopes=GC,
  label="Selisih bayar yang dianggap lunas",
  help="Selisih rupiah antara uang masuk dan tagihan yang masih dianggap wajar (mis. biaya transfer). Dalam batas "
       "ini tagihan langsung dianggap lunas dan selisihnya dicatat sebagai pembulatan. Isi 0 = setiap selisih harus "
       "diputuskan petugas. Bisa dibedakan per pelanggan dari kartu pelanggan.",
  impact="Menentukan kapan pelanggan langsung dianggap lunas walau nominalnya tidak persis.",
  example="Toleransi Rp 5.000 · tagihan Rp 10.000.000, masuk Rp 9.997.500 → otomatis lunas "
          "(selisih Rp 2.500 jadi beban pembulatan)",
  consumers=("services/payment_variance_service.py:variance_policy",), risk="high",
  related=("payment.variance_writeoff_requires_approval", "payment.variance_underpay_default"))

E("payment.variance_underpay_default", group="pembayaran-pelanggan", section="selisih-bayar", type="enum", default="outstanding",
  options=({"value": "outstanding", "label": "Sisa tetap jadi piutang (aman)"},
           {"value": "reschedule", "label": "Ubah jadwal — sisa jadi cicilan baru"},
           {"value": "writeoff", "label": "Hapus sisa (perlu alasan + persetujuan)"}),
  scopes=GC,
  label="Pilihan bawaan saat pelanggan KURANG bayar",
  help="Pilihan yang disorot lebih dulu di dialog Selisih Pembayaran. Petugas tetap bisa "
       "memilih yang lain — bawaan ini hanya mempercepat keputusan yang paling sering dipakai."
       " Bisa dibedakan per pelanggan dari kartu pelanggan.",
  impact="Mengubah pilihan yang terpilih otomatis di dialog selisih pembayaran.",
  example="Bawaan `Sisa tetap jadi piutang` · kurang Rp 2.000.000 → sisa tetap ditagih",
  consumers=("services/payment_variance_service.py:variance_policy",), risk="medium",
  related=("payment.variance_overpay_default",))

E("payment.variance_overpay_default", group="pembayaran-pelanggan", section="selisih-bayar", type="enum", default="deposit",
  options=({"value": "deposit", "label": "Simpan sebagai saldo pelanggan"},
           {"value": "allocate", "label": "Alokasikan ke pesanan terbuka lain"},
           {"value": "refund", "label": "Kembalikan (kas keluar)"}),
  scopes=GC,
  label="Pilihan bawaan saat pelanggan LEBIH bayar",
  help="Perlakuan bawaan untuk kelebihan uang: disimpan sebagai saldo pelanggan, dipakai melunasi pesanan terbuka "
       "lain, atau dikembalikan lewat kas keluar. Bisa dibedakan per pelanggan dari kartu pelanggan.",
  impact="Mengubah pilihan yang terpilih otomatis saat ada kelebihan bayar.",
  example="Bawaan 'Simpan sebagai saldo pelanggan' · lebih Rp 1.500.000 → masuk saldo pelanggan",
  consumers=("services/payment_variance_service.py:variance_policy",), risk="medium",
  related=("payment.variance_underpay_default",))

E("payment.variance_writeoff_requires_approval", group="pembayaran-pelanggan", section="selisih-bayar", type="bool", default=True,
  scopes=G,
  label="Penghapusan sisa kurang bayar wajib disetujui",
  help="Bila aktif, menghapus sisa piutang karena kurang bayar (di luar toleransi) hanya "
       "boleh dilakukan peran penyetuju — selain wajib memilih label alasan.",
  impact="Mencegah piutang hilang diam-diam lewat dalih 'selisih kecil'.",
  example="Aktif · sales menghapus sisa Rp 500.000 → ditolak, harus Manajer/admin",
  consumers=("services/payment_variance_service.py:variance_policy",), risk="high",
  related=("payment.variance_writeoff_approver_role", "payment.variance_writeoff_max_amount"))

E("payment.variance_writeoff_approver_role", group="pembayaran-pelanggan", section="selisih-bayar", type="enum", default="manager",
  options=({"value": "manager", "label": "Manajer"}, {"value": "admin", "label": "Admin / Direksi"}),
  scopes=G,
  label="Siapa yang boleh menghapus sisa kurang bayar",
  help="Peran minimum yang berwenang memutuskan penghapusan sisa piutang & pengembalian dana.",
  impact="Menentukan siapa yang boleh menekan tombol Hapus Sisa / Kembalikan Dana.",
  example="Manajer · sales hanya bisa memilih `sisa tetap piutang` atau `ubah jadwal`",
  consumers=("services/approval_policy_service.py:default_rows_for",), risk="high",
  related=("payment.variance_writeoff_requires_approval",),
  # KP-T4 — isi kunci ini pindah ke tabel kebijakan persetujuan (`approval_policies`).
  status="not_used", not_used_reason=_KPT4_TIDAK_DIPAKAI)

# PK-38 — hapus sisa kini dibatasi `kontrol.pengurang_piutang.batas_nominal` (orang kedua, bukan "harus admin"). Kunci ini
# tetap berlaku untuk pengembalian dana & tutup sisa hutang pemasok (perilaku hari ini), dan menjadi cadangan batas
# pengurang piutang selama kunci baru belum pernah diisi (`services/ar_reduction_guard.py:batas`).
E("payment.variance_writeoff_max_amount", group="pembayaran-pelanggan", section="selisih-bayar", type="money", default=1000000,
  min=0, max=1000000000, step=100000, unit="Rp", scopes=G,
  label="Batas pengembalian dana oleh Manajer",
  help="Di atas nilai ini pengembalian kelebihan bayar pelanggan dan penutupan sisa hutang pemasok hanya boleh oleh "
       "admin/direksi. Selama batas pengurang piutang tanpa uang masuk belum pernah diisi, nilai ini juga dipakai "
       "sebagai batas itu. Isi 0 bila tidak ingin membatasi.",
  impact="Membatasi uang yang bisa dikembalikan satu Manajer tanpa eskalasi.",
  example="Rp 1.000.000 · Manajer mengembalikan kelebihan bayar Rp 3.000.000 → ditolak, harus admin",
  consumers=("services/payment_variance_service.py:variance_policy", "services/ar_reduction_guard.py:batas"),
  risk="high",
  related=("payment.variance_writeoff_approver_role", "kontrol.pengurang_piutang.batas_nominal"))

E("payment.variance_reschedule_days", group="pembayaran-pelanggan", section="selisih-bayar", type="int", default=14,
  min=1, max=365, step=1, unit="hari", scopes=G,
  label="Perpanjangan tempo bawaan saat jadwal diubah",
  help="Saat sisa kurang bayar dijadikan cicilan baru, tanggal jatuh temponya diusulkan "
       "sekian hari dari hari ini. Petugas tetap bisa memilih tanggal lain.",
  impact="Mengubah tanggal usulan pada pilihan `Ubah jadwal`.",
  example="14 hari · keputusan hari ini 10 Juli → cicilan sisa jatuh tempo 24 Juli",
  consumers=("services/payment_variance_service.py:variance_policy",), risk="low",
  related=("payment.variance_underpay_default",))

E("payment.variance_refund_method", group="pembayaran-pelanggan", section="selisih-bayar", type="enum", default="transfer",
  options=({"value": "transfer", "label": "Transfer bank (Kas Besar)"},
           {"value": "cash", "label": "Tunai (Kas Kecil)"}),
  scopes=G,
  label="Cara bawaan mengembalikan kelebihan bayar",
  help="Menentukan kas mana yang dipakai saat kelebihan bayar dikembalikan ke pelanggan.",
  impact="Menentukan buku kas yang berkurang saat pengembalian dana.",
  example="Transfer bank · pengembalian Rp 1.000.000 keluar dari Kas Besar",
  consumers=("services/payment_variance_service.py:variance_policy",), risk="medium",
  related=("payment.variance_overpay_default",))

E("payment.variance_ap_tolerance_rupiah", group="pembelian", section="tagihan", type="money", default=5000,
  min=0, max=10000000, step=1000, unit="Rp", scopes=G,
  label="Selisih bayar ke pemasok yang dianggap lunas",
  help="Selisih kecil saat kita membayar tagihan pemasok (pembulatan, biaya transfer) yang masih dianggap lunas. "
       "Isi 0 = setiap selisih harus diputuskan petugas.",
  impact="Menentukan kapan tagihan pemasok dianggap lunas walau kurang/lebih sedikit.",
  example="Toleransi Rp 5.000 · tagihan Rp 8.000.000 dibayar Rp 7.998.000 → tagihan LUNAS",
  consumers=("services/payment_variance_service.py:variance_policy",), risk="high",
  related=("payment.variance_tolerance_rupiah",))
