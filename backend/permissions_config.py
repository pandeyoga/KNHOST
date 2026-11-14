DEFAULT_PERMISSIONS = {
    "admin": {
        "field_visibility": ["grade", "lot", "origin"],   # L01 LN-012 — lihat atribut stok
        "goods_receipt": ["view", "create", "count", "review", "close", "approve", "configure"],   # GRN Fase 2 — Kedatangan Barang (§4.7)
        "marketing": ["view", "create", "update", "approve", "delete"],
        "product": ["view", "create", "update", "delete", "import", "export"],
        "color": ["view", "create", "update", "delete", "approve"],
        "makloon": ["view", "create", "update", "delete", "configure"],   # KF-T1 — "configure" = ubah pengaturan modul ini di Pusat Pengaturan
        "makloon_order": ["view", "create", "issue", "receive", "cancel", "claim", "claim_approve"],
        "supplier_contract": ["view", "create", "update", "delete"],
        "supplier_item": ["view", "create", "update", "delete", "import"],
        "process_recipe": ["view", "create", "update", "delete"],
        "production": ["view", "manage_bom", "create", "release", "complete", "cancel"],
        "scheduler": ["view", "run", "configure"],
        "customer": ["view", "create", "update", "delete", "import", "export"],
        "warehouse": ["view", "create", "update", "delete", "import", "export"],
        "uom": ["view", "create", "update", "delete", "import", "export"],
        "template": ["view", "create", "update", "delete", "print", "import", "export"],
        "order": ["view", "create", "update", "delete", "approve", "confirm", "print",
                  "deliver", "verify", "exact_cut", "override", "cancel", "approve_price_edit"],
        "sample_order": ["view", "create", "approve_payment", "confirm", "cancel", "cutting_config", "cutting_receive"],
        "wms": ["view", "create", "update", "scan", "dispatch", "print", "approve", "untagged_override"],
        "document": ["view", "create", "print"],
        "user": ["view", "create", "update", "delete"],
        "permission": ["view", "update"],
        # FASE E-0 (E0.3) — jejak audit punya resource izin SENDIRI. Sebelumnya
        # digerbang `product.view` sehingga sales & gudang membaca jejak SELURUH grup (L7).
        "audit": ["view"],
        # FASE E-0 (E0.8f) — sisi UANG antar-PT dipisah dari sisi BARANG.
        # `interco` (view/ship/receive) = aliran barang → boleh gudang.
        # `interco_finance` = saldo pasangan PT, pelunasan, laporan margin, penagihan
        #   → HANYA admin/manager (L20: gudang sebelumnya bisa membacanya).
        "interco_finance": ["view"],
        # FIX-3a — `approve_value`: langkah 2 pendaftaran awal (nilai & jurnal, sesudah hitungan disetujui gudang).
        "inventory": ["view", "create", "update", "cycle_count", "approve_count", "approve_value", "pegging", "configure"],   # KF-T1 — "configure" = ubah pengaturan modul ini di Pusat Pengaturan
        "reports": ["view", "export"],
        "label": ["view", "generate"],
        "transfer": ["view", "create", "update", "approve", "reject", "complete", "cancel"],
        "entity": ["view", "create", "update", "delete"],
        "price_approval": ["view", "create", "update", "delete", "approve", "reject"],
        "tax_invoice": ["view", "create", "update", "replace", "cancel", "print"],
        "sales_return": ["view", "create", "update", "approve", "reject", "policy"],
        # FASE F-6 — `approval.approve` DICABUT: satu-satunya endpoint yang memeriksanya
        # (`POST /approval-requests/{id}/approve|reject`) dipensiunkan karena mesin
        # persetujuan generiknya tak pernah punya produsen. Keputusan nyata dijaga izin
        # dokumennya masing-masing (`order.approve`, `transfer.approve`, dst).
        "approval": ["view"],
        "settings": ["view", "manage"],
        # FASE G-1 — amandemen dokumen finansial (koreksi ber-alasan & ber-persetujuan)
        "finance_amendment": ["propose", "approve", "admin"],
        # FASE G-2 — rencana pembayaran fleksibel + denda sebagai dokumen
        "payment_plan": ["view", "create", "update", "void"],
        "penalty": ["view", "issue", "waive", "adjust", "pay"],
        # FASE G-3 — keputusan selisih pembayaran (lebih/kurang bayar)
        "payment_variance": ["view", "decide"],
        # FASE G-9 — pusat kasus keuangan (uang nyangkut: salah transfer, dobel, giro ditolak)
        "finance_case": ["view", "create", "resolve", "admin"],
        # FASE G-7 — kontrabon: siklus tukar faktur supplier (gabung faktur, potongan, bayar)
        "contra_bon": ["view", "create", "update", "verify", "approve", "pay"],
        # FASE G-6 — transaksi antar-PT (jual-beli) + settlement/netting (admin: semua aksi)
        # FASE G-6b — `return` (retur antar-PT) & `tax` (faktur pajak internal).
        "interco": ["view", "create", "update", "approve", "ship", "receive", "invoice",
                    "cancel", "settle", "return", "tax"],
        # 2026-10 — penetap HARGA INTERNAL antar-PT (keputusan pemilik: MD, Finance, Admin).
        "interco_price": ["view", "set"],
        # FASE E-7 (E7d) — Permintaan Internal: admin menindak antrean (jadikan
        # transaksi antar-PT / tolak dengan alasan).
        "internal_request": ["view", "create", "cancel", "reject", "convert"],
        # FASE D — PERMINTAAN DESAIN (`<ENT>/DSR-#####`): penugasan desain,
        # serah artwork, dan keputusan ACC/revisi ber-alasan.
        "design_request": ["view", "create", "update", "assign", "deliver",
                           "decide", "cancel", "report"],
        # FASE I — INSPEKSI & QC SEBAGAI DOKUMEN (`<ENT>/INS-#####`): SPK petugas,
        # hasil warna & handfeel dibanding sample yang di-ACC, lalu keputusan.
        "inspection": ["view", "create", "assign", "inspect", "decide", "reopen"],
        # FASE F — R&D & Desain (spesifikasi · labdip/proofing · pattern · rilis produk)
        # `hold` (2026-09) — menahan desain yang sudah ACC agar tidak masuk proofing R&D.
        "rnd": ["view", "create", "submit", "assess", "decide", "manage", "hold"],
        "supplier": ["view", "create", "update", "delete"],
        # PK-17 — `configure` = membuat/mengubah rekening kas & bank (dulu ikut `create` pencatat transaksi).
        "cash": ["view", "create", "delete", "configure"],
        "fixed_asset": ["view", "create", "update", "run", "dispose"],
        "budget": ["view", "create", "update", "delete", "configure"],
        "purchase_order": ["view", "create", "update", "approve", "reject"],
        "purchase_return": ["view", "create", "update", "approve", "reject"],
        "purchase_requisition": ["view", "create", "update", "approve", "reject"],
        "vendor_bill": ["view", "create", "update", "approve", "reject", "pay"],
        "landed_cost": ["view", "create", "update", "approve", "reject", "pay"],
        "input_tax": ["view", "create", "cancel"],
        "rfq": ["view", "create", "update", "award"],
        "ar_receipt": ["view", "create", "void"],
        "accounting": ["view", "create", "void", "manage"],
        # FASE G-5 — buka periode tertutup: usul/setujui (unlock) + posting mundur (backdate).
        "period": ["unlock", "backdate"],
        "pricelist": ["view", "manage"],
        "hr": ["view", "create", "update", "delete", "view_pii", "manage_org", "manage_settings", "manage_attendance", "manage_payroll"],
        "cash_advance": ["view", "create", "update", "submit", "approve", "reject", "disburse"],
        "cash_settlement": ["view", "create", "update", "submit", "approve", "reject", "manage"],
        "vehicle_log": ["view", "create", "update", "delete"],
        "pdf_template": ["view", "manage"],
        "esign": ["view", "sign", "manage"],
        "document_delivery": ["view", "send", "manage"],
        "logistics": ["view", "manage", "update"],   # FB-02
    },
    "sales": {
        "sales_pov": ["commercial"],   # L01 LN-012 — POV komersial: grade selalu tersembunyi
        "marketing": ["view", "create", "update"],
        "product": ["view"],
        # FASE F — sales boleh MENGAJUKAN permintaan sample untuk pelanggan
        # (mis. minta labdip warna khusus), tetapi tidak menilai/memutus.
        "rnd": ["view", "create"],
        "color": ["view", "create"],
        # Fase D — sales HANYA view (traceability & recall output makloon).
        # Tarif/kontrak mitra (supplier_contract) TETAP tertutup: data komersial.
        "makloon": ["view"],
        "makloon_order": ["view"],
        "customer": ["view", "create", "update"],
        "warehouse": ["view"],
        "uom": ["view"],
        "template": ["view"],
        "order": ["view", "create", "update", "print", "cancel"],
        "sample_order": ["view", "create", "cancel"],
        # FASE G-1 — sales boleh MENGAJUKAN koreksi (bukan menyetujui).
        "finance_amendment": ["propose"],
        "payment_plan": ["view"],
        "penalty": ["view"],
        # FASE E-8 (E8.2) — keputusan SELISIH BAYAR (lebih/kurang bayar) pindah ke
        # peran `finance`. Sales yang menagih tidak boleh sekaligus memutus selisihnya.
        "payment_variance": ["view"],
        # FASE G-9 — sales boleh MELAPORKAN kasus (mis. pelanggan bilang sudah transfer) &
        # melihat perkembangannya, tetapi TIDAK boleh menutup kasus uang.
        "finance_case": ["view", "create"],
        "document": ["view", "create", "print"],
        "inventory": ["view"],
        "price_approval": ["view", "create", "update"],
        # FASE E-8 (E8.2) — PEMISAHAN TUGAS (keputusan pemilik E8.10b#2). Yang mencatat
        # UANG MASUK (kwitansi AR) dan menerbitkan FAKTUR PAJAK adalah peran `finance`,
        # bukan orang yang juga membuat pesanan & menyepakati harga. Sales tetap boleh
        # MELIHAT (dia yang ditanya pelanggan "faktur saya sudah keluar belum?"),
        # tetapi tidak lagi menerbitkan faktur pajak.
        "tax_invoice": ["view"],
        "sales_return": ["view", "create", "update"],
        # Sales mencatat kwitansi dari HP (keputusan Sesi 16, K-36); `void` dan keputusan selisih tetap Finance.
        "ar_receipt": ["view", "create"],
        "pricelist": ["view"],
        "cash_advance": ["view", "create", "update", "submit"],
        "cash_settlement": ["view", "create", "update", "submit"],
        "vehicle_log": ["view", "create"],
        "esign": ["view", "sign"],
        "document_delivery": ["view", "send"],
        "logistics": ["view"],   # FB-02 — sales membaca pelacakan, tidak mengubah
        # FASE E-7 (E7d) — jalur yang hilang untuk sales: papan stok memberi isyarat
        # "tersedia di badan usaha lain", tetapi seluruh menu Antar Entitas 403 untuk
        # sales. Sales boleh MENGAJUKAN permintaan & membatalkan miliknya; yang
        # menjadikannya transaksi antar-PT tetap admin/manajer (E-8: `sales_admin`).
        "internal_request": ["view", "create", "cancel"],
    },
    "manager": {
        "field_visibility": ["grade", "lot", "origin"],   # L01 LN-012 — lihat atribut stok
        "goods_receipt": ["view", "review", "close", "approve", "configure"],   # GRN Fase 2 — Kedatangan Barang (§4.7)
        "logistics": ["view"],   # Integrasi FIX-1 (B1b UI-47) — manajer memantau pengiriman (baca saja), menu Pengiriman berfungsi
        "marketing": ["view", "create", "update", "approve", "delete"],
        "product": ["view", "export"],
        # FASE F — manager: menilai spesifikasi, memutus pemenang sample, mengubah kebijakan R&D, hold desain ACC
        "rnd": ["view", "create", "submit", "assess", "decide", "manage", "hold"],
        "color": ["view", "create", "update", "delete", "approve"],
        "makloon": ["view", "create", "update", "delete", "configure"],   # KF-T1 — "configure" = ubah pengaturan modul ini di Pusat Pengaturan
        "makloon_order": ["view", "create", "issue", "receive", "cancel", "claim", "claim_approve"],
        "supplier_contract": ["view", "create", "update", "delete"],
        "supplier_item": ["view", "create", "update", "delete", "import"],
        "process_recipe": ["view", "create", "update", "delete"],
        "production": ["view", "manage_bom", "create", "release", "complete", "cancel"],
        "scheduler": ["view", "run"],
        "customer": ["view", "create", "update", "export"],
        "warehouse": ["view", "create", "update", "export"],
        "uom": ["view"],
        "template": ["view"],
        "order": ["view", "create", "update", "approve", "confirm", "print", "deliver", "verify", "exact_cut",
                  "override", "cancel", "approve_price_edit"],
        "sample_order": ["view", "create", "approve_payment", "confirm", "cancel", "cutting_config", "cutting_receive"],
        "wms": ["view", "create", "update", "scan", "dispatch", "print", "approve", "untagged_override"],
        "document": ["view", "create", "print"],
        "inventory": ["view", "cycle_count", "approve_count", "approve_value", "update", "pegging", "configure"],   # KF-T1 — "configure" = ubah pengaturan modul ini di Pusat Pengaturan
        "reports": ["view", "export"],
        "label": ["view", "generate"],
        "transfer": ["view", "create", "approve", "reject", "complete"],
        "entity": ["view"],
        "price_approval": ["view", "create", "update", "approve", "reject"],
        "tax_invoice": ["view", "create", "update", "replace", "cancel", "print"],
        "sales_return": ["view", "create", "update", "approve", "reject", "policy"],
        # FASE F-6 — `approval.approve` DICABUT: satu-satunya endpoint yang memeriksanya
        # (`POST /approval-requests/{id}/approve|reject`) dipensiunkan karena mesin
        # persetujuan generiknya tak pernah punya produsen. Keputusan nyata dijaga izin
        # dokumennya masing-masing (`order.approve`, `transfer.approve`, dst).
        "approval": ["view"],
        "settings": ["view"],
        # FASE E-0 (E0.8f) — manajer ikut memegang sisi UANG antar-PT.
        "interco_finance": ["view"],
        "finance_amendment": ["propose", "approve"],
        "payment_plan": ["view", "create", "update", "void"],
        "penalty": ["view", "issue", "waive", "adjust", "pay"],
        # FASE G-3 — keputusan selisih pembayaran (lebih/kurang bayar)
        "payment_variance": ["view", "decide"],
        # FASE G-9 — manager adalah penyetuju bawaan penyelesaian kasus keuangan
        # (ambang & batas nominalnya diatur `case.require_approval_above` / `case.refund_max_amount`).
        "finance_case": ["view", "create", "resolve"],
        # FASE G-7 — manager membuat, memverifikasi & menyetujui kontrabon. Kontrabon di atas
        # `contra_bon.approval_threshold_rupiah` tetap butuh admin (dijaga service, bukan matrix).
        "contra_bon": ["view", "create", "update", "verify", "approve", "pay"],
        # FASE G-6 — manager: buat/kirim/terima/faktur transaksi antar-PT + settlement
        # (ambang bernilai besar tetap butuh admin, dijaga service).
        # FASE G-6b — manager boleh mengajukan retur & menerbitkan faktur pajak internal.
        "interco": ["view", "create", "update", "approve", "ship", "receive", "invoice",
                    "cancel", "settle", "return", "tax"],
        # FASE E-7 (E7d) — manajer menindak antrean permintaan internal.
        "internal_request": ["view", "create", "cancel", "reject", "convert"],
        # FASE D — PERMINTAAN DESAIN (`<ENT>/DSR-#####`): penugasan desain,
        # serah artwork, dan keputusan ACC/revisi ber-alasan.
        "design_request": ["view", "create", "update", "assign", "deliver",
                           "decide", "cancel", "report"],
        # FASE I — INSPEKSI & QC SEBAGAI DOKUMEN: manajer menugaskan, memutuskan, dan
        # **satu-satunya** yang boleh melepas tahanan barang (keputusan pemilik #5).
        "inspection": ["view", "create", "assign", "inspect", "decide", "reopen"],
        "supplier": ["view", "create", "update", "delete"],
        # PK-17 — `configure` = membuat/mengubah rekening kas & bank (dulu ikut `create` pencatat transaksi).
        "cash": ["view", "create", "delete", "configure"],
        "fixed_asset": ["view", "create", "update", "run", "dispose"],
        "budget": ["view", "create", "update", "delete"],
        "purchase_order": ["view", "create", "update", "approve", "reject"],
        "purchase_return": ["view", "create", "update", "approve", "reject"],
        "purchase_requisition": ["view", "create", "update", "approve", "reject"],
        "vendor_bill": ["view", "create", "update", "approve", "reject", "pay"],
        "landed_cost": ["view", "create", "update", "approve", "reject", "pay"],
        "input_tax": ["view", "create", "cancel"],
        "rfq": ["view", "create", "update", "award"],
        "ar_receipt": ["view", "create", "void"],
        "accounting": ["view", "create", "void", "manage"],
        # FASE G-5 — manager ikut boleh usul/setujui unlock & posting mundur (dual-control).
        "period": ["unlock", "backdate"],
        "pricelist": ["view", "manage"],
        "hr": ["view", "create", "update", "delete", "view_pii", "manage_org", "manage_attendance", "manage_payroll"],
        "cash_advance": ["view", "create", "update", "submit", "approve", "reject"],
        "cash_settlement": ["view", "create", "update", "submit", "approve", "reject", "manage"],
        "vehicle_log": ["view", "create", "update", "delete"],
        "pdf_template": ["view", "manage"],
        "esign": ["view", "sign", "manage"],
        "document_delivery": ["view", "send", "manage"],
        # AUDIT SALES vs ADMIN SALES / PERAN (2026-08-15) — manajer HANYA-BACA daftar akun.
        # Bukti: layar "Karyawan" (`hr-employees`, menu resmi manajer) mengambil
        # `GET /users` untuk kolom **akun tertaut** (FASE E-2: akun ditaut ke karyawan).
        # Manajer tidak punya `user.view` sehingga panggilan itu 403 lalu ditelan
        # `.catch(() => ({data: []}))` → kolomnya kosong TANPA satu pun pesan: manajer
        # menyimpulkan "karyawan ini belum punya akun" padahal punya.
        # MEMBUAT/mengubah/menghapus akun tetap milik admin (create/update/delete TIDAK diberi).
        "user": ["view"],
    },
    # ═══════════════════════════════════════════════════════════════════════════
    # FASE E-8 (E8.1b) — DUA PERAN BARU. Sampai E-7 orang yang mengurus keseluruhan
    # pesanan harus dijadikan `sales` (tak bisa Konfirmasi SO) atau `manager` (ikut
    # dapat kuasa tutup buku, payroll, bayar tagihan supplier, hapus master).
    # Registry peran: `backend/role_registry.py`.
    # ═══════════════════════════════════════════════════════════════════════════
    "sales_admin": {
        "field_visibility": ["grade", "lot", "origin"],   # L01 LN-012 — lihat atribut stok
        "marketing": ["view", "create", "update"],
        # ADMIN SALES — pemilik alur pesanan end-to-end: validasi → keputusan
        # pemenuhan (stok sendiri · ambil dari PT lain · reorder supplier) →
        # konfirmasi → dokumen → memproses retur.
        # TIDAK punya: tax_invoice · ar_receipt · payment_variance.decide · cash ·
        # accounting · vendor_bill (sisi uang & pajak tetap `finance`/manager/admin).
        # REVISI SAMPEL — pesanan sample BUKAN meja ini (hanya lihat).
        "sample_order": ["view"],
        "product": ["view"],
        "color": ["view"],
        "customer": ["view", "create", "update"],
        "warehouse": ["view"],
        "uom": ["view"],
        "template": ["view"],
        "pricelist": ["view"],
        "reports": ["view"],
        # `confirm` = wewenang yang dulu memaksa orang ini dijadikan manajer.
        # `deliver` = menandai pesanan terkirim (keputusan pemilik E8.10b#3:
        # boleh gudang MAUPUN Admin Sales; dicabut dari sales).
        # `verify` (E8.13) = VERIFIKASI ADMINISTRATIF — kelengkapan alamat/syarat bayar/
        # PPN/NPWP. SENGAJA dipisah dari `approve` (nilai · kredit · harga khusus) yang
        # tetap milik manajer: dulu satu-satunya gerbang adalah persetujuan nilai,
        # sehingga pemeriksaan rutin ikut menumpuk di meja manajer dan tidak ada catatan
        # siapa yang sudah memeriksa kelengkapannya.
        "order": ["view", "create", "update", "confirm", "print", "deliver", "verify", "exact_cut",
                  "override", "cancel"],
        "document": ["view", "create", "print"],
        # `pegging` (menahan roll untuk pelanggan/pesanan tertentu) = KEPUTUSAN
        # PEMENUHAN, dicabut dari `sales` di E8.2 dan diberikan ke peran ini.
        "inventory": ["view", "pegging"],
        "wms": ["view"],                       # memantau progres gudang, tanpa aksi
        "price_approval": ["view", "create", "update"],   # approve → manajer
        "sales_return": ["view", "create", "update"],     # approve → manajer
        "purchase_requisition": ["view", "create", "update"],  # reorder ke supplier
        # Antar-PT: boleh membuat & menagihkan; `settle`/`cancel` tetap manajer.
        "interco": ["view", "create", "update", "invoice"],
        # E8.8 — antrean Permintaan Internal (PIN) memang milik Admin Sales.
        "internal_request": ["view", "create", "cancel", "reject", "convert"],
        # FASE D — Admin Sales MEMINTA desain dari pesanan pelanggannya
        # (keputusan ACC tetap manajer/admin).
        "design_request": ["view", "create"],
        # FASE I — Admin Sales MEMANTAU inspeksi retur pelanggannya (tanpa aksi):
        # pertanyaan pelanggan "barang saya sudah diperiksa belum?" dijawab di sini.
        "inspection": ["view"],
        "transfer": ["view", "create"],        # approve → manajer/gudang
        "approval": ["view"],                  # melihat antrean, tanpa menyetujui
        "finance_amendment": ["propose"],
        "payment_plan": ["view", "create", "update"],   # void/pembebasan → manajer
        "penalty": ["view"],
        "finance_case": ["view", "create"],
        "esign": ["view", "sign"],
        "document_delivery": ["view", "send"],
        "logistics": ["view", "manage", "update"],   # FB-02 — manajer
        "cash_advance": ["view", "create", "update", "submit"],
        "cash_settlement": ["view", "create", "update", "submit"],
        "vehicle_log": ["view", "create"],
        "rnd": ["view"],
        "makloon_order": ["view"],
        # ─── HANYA-LIHAT, ditambah setelah AUDIT SALES vs ADMIN SALES ──────────
        # (`scripts/audit_sales_roles_ux.py`, sesi 2026-08-15). Empat izin di bawah
        # BUKAN pelebaran wewenang: semuanya `view` saja, dan semuanya menutup
        # LAYAR MATI yang terbukti — menu/tab yang memang diberikan ke peran ini
        # tetapi datanya 403 sehingga pengguna menabrak dinding tanpa penjelasan.
        #
        # `supplier`/`supplier_item` — keputusan pemilik E8.10b#4 memberi Admin Sales
        #   kuasa penuh "reorder ke supplier" (membuat PR). Tanpa membaca daftar
        #   pemasok & item pemasok, pemilih pemasok di formulir PR kosong dan
        #   `preferred_supplier_id` tak bisa diisi — kuasa yang diberikan di atas
        #   kertas tidak bisa dipakai di layar.
        # `tax_invoice` — panel detail pesanan (layar utama peran ini) membaca
        #   `GET /tax-invoices?order_id=…` untuk menunjukkan faktur pajaknya SUDAH
        #   terbit atau belum. Peran `sales` sudah punya `view`; tanpa ini Admin
        #   Sales melihat "belum ada faktur" padahal ada — kegagalan SENYAP
        #   (kesalahan gagal ditampilkan; `.catch` mengubah 403 jadi daftar kosong).
        #   MENERBITKAN faktur tetap milik `finance` (tidak ada `create` di sini).
        # `ar_receipt` — panel riwayat uang masuk di Worklist Penagihan. `sales`
        #   pun sudah boleh MELIHAT. CATATAN: sejak Sesi 16, `bootstrap.GRANT`
        #   menambahkan `ar_receipt.create` untuk `sales` (kwitansi dari HP) di matriks
        #   DB — `void` & keputusan selisih tetap milik `finance`.
        "supplier": ["view"],
        "supplier_item": ["view"],
        "tax_invoice": ["view"],
        "ar_receipt": ["view"],
    },
    "finance": {
        "field_visibility": ["grade", "lot", "origin"],   # L01 LN-012 — lihat atribut stok
        # FIX-3a (keputusan koordinator, persetujuan dua langkah) — Finance menyetujui NILAI & JURNAL pendaftaran awal
        # gedung sesudah gudang menyetujui hitungan. Hanya aksi itu (+ membaca sesi pendaftaran); tidak ada izin stok lain.
        "inventory": ["approve_value"],
        "goods_receipt": ["view"],   # GRN Fase 2 — Kedatangan Barang (§4.7)
        # REVISI SAMPEL — Finance menyetujui PEMBAYARAN sample berbayar (bersama Admin Sample).
        "sample_order": ["view", "approve_payment"],
        # KASIR / FINANCE — sisi UANG MASUK & PAJAK KELUARAN.
        # CATATAN: sisi HUTANG (vendor_bill.pay, contra_bon, landed_cost) TETAP
        # manajer/admin sampai pemilik memutuskan sebaliknya — jangan diperluas sendiri.
        # MN-T1 — pemilik memutuskan K-17: lihat + bayar tagihan & kontrabon ditambahkan blok MN-T1 di akhir berkas
        # (landed cost tetap manajer/admin).
        # PK-38 (K-17, keputusan pemilik) — `contra_bon` view + pay ditambahkan di blok PK-38 di bawah.
        "product": ["view"],
        "customer": ["view"],
        "template": ["view"],
        "pricelist": ["view"],
        "reports": ["view"],
        # FASE U (dua satuan) — KOSAKATA SATUAN, HANYA-LIHAT. Bukan tambalan:
        # FASE U menaruh `<QtyDual/>` ("12 roll · 540 yard") di hampir SEMUA tabel,
        # termasuk yang memang wilayah finance — faktur pajak, piutang, nota kredit,
        # kwitansi. Sejak INV-UOM-02 aturan D melarang daftar satuan DIKETIK di
        # layar, kata satuan hanya boleh datang dari server
        # (`GET /api/uom-conversions/catalog`, `require_permission("uom","view")`).
        # Bukti terukur 2026-08-20 tanpa izin ini: `audit_sales_roles_ux` memerah
        # "PANEL MATI finance → /uom-conversions/catalog" karena layar
        # *Pelanggan & CRM* — menu RESMI finance untuk menagih (`roles.js`) — memuat
        # `IncentiveRatesEditor` yang memanggil katalog itu lewat `useUomConversions`.
        # HANYA `view`: menambah/mengubah baris satuan tetap milik admin.
        "uom": ["view"],
        "order": ["view", "print", "approve_price_edit"],   # 2026-10 — setujui harga/diskon override
        "document": ["view", "print"],
        "sales_return": ["view"],
        # LN-140 — finance PT pemasok wajib melihat retur antar-PT & nilainya (Meja retur internal).
        "interco": ["view"],
        "interco_finance": ["view"],
        "ar_receipt": ["view", "create"],      # void → manajer
        "tax_invoice": ["view", "create", "update", "replace", "print"],   # cancel → manajer
        "payment_variance": ["view", "decide"],  # batas nominal tetap dijaga config
        # Papan antrean persetujuan (`/approvals/backlog`) — finance memutus selisih bayar &
        # menyetujui pembayaran sample, jadi ia harus MELIHAT antreannya (tanpa menyetujui SO).
        "approval": ["view"],
        "penalty": ["view", "issue"],          # waive/adjust → manajer
        "payment_plan": ["view", "update"],
        "cash": ["view", "create", "configure"],   # PK-17 — `configure` = kelola rekening kas & bank
        "accounting": ["view"],
        "finance_case": ["view", "create"],
        "finance_amendment": ["propose"],
        # 2026-09 (sesi #075) — antrean "Hutang supplier jatuh tempo" di Meja Finance menaut ke
        # layar PO. HANYA-LIHAT: bayar/kontrabon/landed cost tetap manajer/admin (lihat catatan atas).
        "purchase_order": ["view"],
        "esign": ["view", "sign"],
        "document_delivery": ["view", "send"],
        "logistics": ["view"],   # FB-02 — admin sales memantau
        "cash_advance": ["view", "create", "update", "submit"],
        "cash_settlement": ["view", "create", "update", "submit"],
        # AUDIT SALES vs ADMIN SALES / PERAN (2026-08-15) — Finance HANYA-BACA master supplier.
        # Bukti: "Kasus Keuangan" (`finance-cases`) adalah menu RESMI peran ini, dan
        # `FinanceCasesView.loadRefs()` mengambil `/suppliers` di dalam SATU `Promise.all`
        # bersama playbook, alasan, kebijakan, pelanggan, dan rekening. Tanpa izin ini
        # panggilan itu 403 → **seluruh** `Promise.all` gagal → playbook/pelanggan/
        # rekening kosong dan layar disambut bilah merah, padahal semua data lainnya
        # boleh dibaca. Nama lawan-transaksi memang dibutuhkan: kasus uang bisa
        # menyangkut supplier ("supplier bilang sudah kami bayar").
        # SISI HUTANG TETAP TERTUTUP: `vendor_bill`, `contra_bon`, `landed_cost` TIDAK
        # diberikan (keputusan pemilik E8.1b) — ini hanya master nama, read-only.
        "supplier": ["view"],
        "interco_price": ["view", "set"],   # 2026-10 — penetap harga internal antar-PT
        # KP-T4 (K-47) — Finance SUDAH menyetujui/menolak tagihan vendor KAMPANYE lewat nama peran (pintu itu dulu
        # tanpa izin). Kini izin + Aturan Persetujuan: `vendor_bill.approve|reject` dibutuhkan pintunya, dan baris
        # Aturan Persetujuan membatasi Finance ke jenis `vendor_bill.kampanye` saja (tagihan pemasok biasa ≥ Manajer).
        # Tanpa `view` → menu hutang tetap tertutup.
        "vendor_bill": ["approve", "reject"],
    },
    "warehouse": {
        "field_visibility": ["grade", "lot", "origin"],   # L01 LN-012 — lihat atribut stok
        "goods_receipt": ["view", "create", "count"],   # GRN Fase 2 — Kedatangan Barang (§4.7)
        "product": ["view"],
        # FASE I — petugas Bagian Inspect: MENGISI hasil (cacat · warna · handfeel).
        # `decide`/`assign` TIDAK diberikan: keputusan terima/tolak dan pelepasan
        # tahanan warna adalah wewenang manajer (keputusan pemilik #5).
        "inspection": ["view", "inspect"],
        # FASE F — warehouse: melihat permintaan sample & MENGELUARKAN bahan sample
        # dari roll (mutasi stok `sample_issue`).
        "rnd": ["view", "submit"],
        "color": ["view"],
        "makloon": ["view"],
        "makloon_order": ["view", "issue", "receive", "claim"],
        "supplier_contract": ["view"],
        "supplier_item": ["view"],
        "process_recipe": ["view"],
        "production": ["view", "create", "release", "complete"],
        "warehouse": ["view", "create", "update"],
        "uom": ["view"],
        "template": ["view"],
        "order": ["view", "deliver"],
        "wms": ["view", "create", "update", "scan", "dispatch", "print"],
        "document": ["view", "create", "print"],
        "inventory": ["view", "cycle_count", "update", "pegging"],
        "label": ["view", "generate"],
        "transfer": ["view", "create", "update"],
        "purchase_order": ["view"],
        "purchase_return": ["view", "create"],
        "purchase_requisition": ["view", "create", "update"],
        # PK-17 (IA-02) — `vendor_bill`, `landed_cost`, `input_tax` (lihat) DICABUT dari bawaan: tidak ada menu gudang
        # untuknya (tab Hutang Pemasok gudang hanya Kontrabon). Matriks tersimpan: `scripts/apply_pk17_role_cleanup.py`.
        # FASE G-7 — gudang IKUT MELIHAT kontrabon: dialah yang tahu barang mana sudah
        # diterima tapi fakturnya belum datang ("GR belum ditagih"). Tidak boleh mengubah uang.
        "contra_bon": ["view"],
        # FASE G-6 — gudang ikut melihat transaksi antar-PT (barang fisik lewat mereka)
        # + boleh menandai ship/receive (aliran barang), tanpa mengubah uang.
        "interco": ["view", "ship", "receive"],
        "rfq": ["view", "create", "update"],
        "vehicle_log": ["view", "create", "update"],
        "esign": ["view", "sign"],
        "document_delivery": ["view", "send"],
        "logistics": ["view", "manage", "update"],   # FB-02 — gudang membuat & mengurus pengiriman
        # AUDIT SALES vs ADMIN SALES / PERAN (2026-08-15) — gudang HANYA-BACA master supplier.
        # Bukti: peran ini SUDAH punya `rfq.create`, `purchase_requisition.create`,
        # `purchase_return.create`, `supplier_contract.view`, `supplier_item.view` —
        # tetapi TIDAK `supplier.view`. Akibatnya di 4 layar resminya (Permintaan
        # Pembelian · RFQ · Retur Beli · Kontrabon) daftar supplier 403 lalu ditelan
        # `.catch(() => ({data: []}))`: dropdown "Supplier" KOSONG tanpa pesan, jadi
        # formulir yang boleh mereka isi tak bisa diselesaikan. Membuat/mengubah master
        # supplier tetap manajer/admin.
        "supplier": ["view"],
    },
    # ═══════════════════════════════════════════════════════════════════════════
    # FASE D (2026-08-20) — PERAN KE-7: **DESAINER**. Keputusan pemilik: desainer
    # menjadi peran ber-AKUN supaya alur "Rina mengunggah artwork-nya sendiri"
    # nyata, bukan diwakilkan admin. Wilayahnya SENGAJA sempit — hanya pekerjaan
    # desain miliknya + galeri karya. Ia tidak menyentuh pesanan, uang, stok,
    # master, maupun keputusan ACC atas karyanya sendiri (pemisahan tugas: yang
    # menilai adalah atasan, seperti aturan KPI Desainer di PS-18).
    # Registry peran: `backend/role_registry.py`; menu: `frontend/src/config/roles.js`.
    # ═══════════════════════════════════════════════════════════════════════════
    "designer": {
        "field_visibility": ["grade", "lot", "origin"],   # L01 LN-012 — lihat atribut stok
        "marketing": ["view", "create", "update"],
        # Permintaan desain: melihat TUGASNYA (pagar kepemilikan di router),
        # menandai mulai dikerjakan, dan menyerahkan artwork. TIDAK boleh
        # `assign`/`decide`/`cancel`.
        "design_request": ["view", "deliver"],
        # Galeri desain & pattern = tempat karyanya hidup. `rnd.view` membuka
        # layar Galeri/Desain; menulis entri galeri lewat pagar `design_request.deliver`
        # (lihat `routers/design_gallery._perm_manage`).
        "rnd": ["view"],
        "product": ["view"],
        # Warna target permintaan diambil dari Pustaka Warna (PantoneFinder).
        "color": ["view"],
        # Catatan sengaja: Profil Saya (ESS) TIDAK butuh izin modul — endpoint
        # "milik saya" (`/hr/employees/me`, `/hr/attendance/me`, `/rnd/reports/my-kpi`)
        # digerbang `current_user`, karena setiap orang berhak melihat datanya sendiri.
    },
    # FB-02 (2026-09-02) — PERAN KE-8: SOPIR / KURIR. Wilayah sempit: modul Logistik saja —
    # memotret muat & bukti terima, mencatat posisi, menandai tahapan. TIDAK membuat pengiriman
    # (itu gudang), tidak menyentuh pesanan/stok/uang.
    # Sesi #087 — MD / Merchandiser: pengembangan produk. TANPA uang, TANPA gudang.
    "md": {
        "field_visibility": ["grade", "lot", "origin"],   # L01 LN-012 — lihat atribut stok
        "product": ["view", "create", "update"],
        "pricelist": ["view", "manage"],
        "price_approval": ["view", "create", "update"],
        "uom": ["view"], "template": ["view"],
        "customer": ["view"],
        "order": ["view"],
        "design_request": ["view", "create", "update", "decide", "assign"],
        "rnd": ["view", "create", "submit", "assess", "decide", "manage"],
        "color": ["view", "create", "update"],
        "supplier": ["view"], "supplier_item": ["view"], "supplier_contract": ["view"],
        "purchase_requisition": ["view", "create", "update"],
        "purchase_order": ["view"],
        "rfq": ["view", "create", "update"],
        "makloon": ["view"], "process_recipe": ["view", "create", "update"],
        "inspection": ["view"],
        "inventory": ["view"],
        "document": ["view", "create", "print"],
        "interco_price": ["view", "set"],   # 2026-10 — penetap harga internal antar-PT
    },
    # Sesi #087 — Admin Gudang: semua wewenang `warehouse` + memimpin (tugaskan SPK,
    # putuskan inspeksi, setujui opname & transfer, kelola logistik). TANPA uang.
    "warehouse_admin": {
        "field_visibility": ["grade", "lot", "origin"],   # L01 LN-012 — lihat atribut stok
        "goods_receipt": ["view", "create", "count", "review", "close", "approve"],   # GRN Fase 2 — Kedatangan Barang (§4.7)
        "product": ["view"],
        "inspection": ["view", "create", "assign", "inspect", "decide", "reopen"],
        "rnd": ["view", "submit"],
        "color": ["view"],
        "makloon": ["view"], "makloon_order": ["view", "issue", "receive", "claim"],
        "supplier": ["view"],  # S#089 — layar PO memuat daftar pemasok (tanpa ini 403 noise)
        "supplier_contract": ["view"], "supplier_item": ["view"], "process_recipe": ["view"],
        "production": ["view", "create", "release", "complete"],
        "warehouse": ["view", "create", "update"],
        "uom": ["view"], "template": ["view"],
        "order": ["view", "deliver"],
        "wms": ["view", "create", "update", "scan", "dispatch", "print", "approve", "untagged_override"],
        "document": ["view", "create", "print"],
        "inventory": ["view", "create", "cycle_count", "approve_count", "update", "pegging"],
        "label": ["view", "generate"],
        "transfer": ["view", "create", "update", "approve", "reject", "complete", "cancel"],
        "purchase_order": ["view"],
        "purchase_return": ["view", "create"],
        "purchase_requisition": ["view", "create", "update"],
        "contra_bon": ["view"],   # PK-17 — vendor_bill/landed_cost/input_tax dicabut dari bawaan (lihat `warehouse`)
        "interco": ["view", "ship", "receive"],
        "rfq": ["view"],
        "vehicle_log": ["view", "create", "update"],
        "esign": ["view", "sign"],
        "document_delivery": ["view", "send"],
        "logistics": ["view", "manage", "update"],
    },
    "driver": {
        "field_visibility": ["grade", "lot", "origin"],   # L01 LN-012 — lihat atribut stok
        "logistics": ["view", "update"],
    },
    # REVISI SAMPEL (2026-09-17) — ADMIN SAMPEL: pemilik alur pesanan sample (SOS-).
    # Menyetujui pembayaran sample berbayar (bersama finance), meneruskan ke gudang
    # (confirm), memantau potong/kirim. TIDAK menyentuh SO roll biasa selain melihat.
    "sample_admin": {
        "field_visibility": ["grade", "lot", "origin"],   # L01 LN-012 — lihat atribut stok
        "product": ["view"],
        "color": ["view"],
        "customer": ["view"],
        "warehouse": ["view"],
        "uom": ["view"],
        "template": ["view"],
        "pricelist": ["view"],
        "order": ["view", "update", "confirm", "print"],
        "sample_order": ["view", "create", "approve_payment", "confirm", "cancel", "cutting_receive"],
        "document": ["view", "create", "print"],
        "inventory": ["view"],
        "wms": ["view"],
        "logistics": ["view"],
    },
}

# P05 IMP-16 (DEC-06, keputusan pemilik 2026-10-12) — MD Quality (warna & handfeel vs sample ACC
# pada penerimaan PO & hasil makloon; lepas/tolak tahanan) dan QC (cacat 4-point, grade, random
# check) sebagai hak akses sendiri. Sementara keduanya melekat ke MD; Admin Gudang tetap ber-QC;
# manajer tetap bisa melepas tahanan sebagai cadangan.
_MDQ_ACTIONS = ["view", "inspect", "decide"]
_QC_ACTIONS = ["view", "inspect", "random_check", "release"]
for _role, _mods in {
    "admin": {"md_quality": _MDQ_ACTIONS, "qc": _QC_ACTIONS},
    "md": {"md_quality": _MDQ_ACTIONS, "qc": _QC_ACTIONS, "warehouse": ["view"]},
    "manager": {"md_quality": ["view", "decide"], "qc": ["view", "release"]},
    "warehouse_admin": {"md_quality": ["view"], "qc": _QC_ACTIONS},
    "warehouse": {"qc": ["view", "inspect"]},
}.items():
    for _m, _a in _mods.items():
        DEFAULT_PERMISSIONS[_role][_m] = sorted(set(DEFAULT_PERMISSIONS[_role].get(_m, [])) | set(_a),
                                                key=lambda a: (a != "view", a))
_QUALITY_BASE = {"inspection": ["view"], "product": ["view"], "color": ["view"], "rnd": ["view"],
                 "inventory": ["view"], "warehouse": ["view"], "supplier": ["view"],
                 "document": ["view", "print"]}
DEFAULT_PERMISSIONS["md_quality"] = {**_QUALITY_BASE, "md_quality": list(_MDQ_ACTIONS)}
# UAT 24 Okt (P1-K1) — kepemilikan desain: klaim diajukan sales/Admin Sales/MD, diputus Manajer.
for _role, _acts in {"sales": ["view", "claim"], "sales_admin": ["view", "claim"], "md": ["view", "claim"],
                     "designer": ["view", "claim"], "finance": ["view"],
                     "manager": ["view", "claim", "decide"], "admin": ["view", "claim", "decide"]}.items():
    if _role in DEFAULT_PERMISSIONS:
        DEFAULT_PERMISSIONS[_role]["design_ownership"] = list(_acts)
DEFAULT_PERMISSIONS["qc"] = {**_QUALITY_BASE, "qc": list(_QC_ACTIONS)}
for _role in ("md_quality", "qc"):
    DEFAULT_PERMISSIONS[_role]["field_visibility"] = ["grade", "lot", "origin"]
# L01 — susut/hilang bahan di mitra: catat & setujui dipisah (owner 2026-10-16).
DEFAULT_PERMISSIONS["admin"]["makloon_order"] += ["record_loss", "approve_loss"]
for _role, _acts in {"manager": ["record_loss", "approve_loss"], "md": ["record_loss"]}.items():
    _cur = DEFAULT_PERMISSIONS[_role].setdefault("makloon_order", ["view"])
    _cur += [x for x in _acts if x not in _cur]
# L01 LN-012 — master grade: hak lihat/tambah/ubah/aktif-nonaktif terpisah.
DEFAULT_PERMISSIONS["admin"]["grade_master"] = ["view", "create", "update", "activate"]
for _role in ("manager", "md", "sales_admin", "warehouse_admin", "md_quality", "qc"):
    DEFAULT_PERMISSIONS[_role]["grade_master"] = ["view"]

# L01 — aksi yang SAH tetapi sengaja tidak dimiliki Admin (katalog aksi = admin + ini).
# L03 LN-030 — lepas HOLD desain = PIC Designer berwenang (bukan setiap pemegang `rnd.hold`).
for _role in ("admin", "manager", "md"):
    DEFAULT_PERMISSIONS[_role]["design_request"] = list(DEFAULT_PERMISSIONS[_role]["design_request"]) + ["release_hold"]
# L03 LN-031 — checklist print paper per ronde (Designer; admin/manager untuk koreksi).
for _role in ("admin", "manager", "designer"):
    DEFAULT_PERMISSIONS[_role]["design_request"] = list(DEFAULT_PERMISSIONS[_role]["design_request"]) + ["paper_check"]
# L03 LN-033 — pemenuhan Pesanan Khusus per item: pilih jalur, menyimpang dari default master,
# realisasi PR→PO/MKO, dan pembatalan adalah hak terpisah (tidak sama dengan rilis master / kunci harga).
DEFAULT_PERMISSIONS["admin"]["od_fulfillment"] = ["view", "choose_route", "override_default", "realize", "cancel"]
DEFAULT_PERMISSIONS["manager"]["od_fulfillment"] = ["view", "choose_route", "override_default", "realize", "cancel"]
DEFAULT_PERMISSIONS["md"]["od_fulfillment"] = ["view", "choose_route", "override_default", "realize"]
for _role in ("sales", "sales_admin", "finance"):
    DEFAULT_PERMISSIONS[_role]["od_fulfillment"] = ["view"]
# UAT 24 Okt (P2-K1/P2.5) — harga Pesanan Khusus: kunci & harga PIC (Admin Sales/Manajer/Admin), biaya kontrak terlihat
# hanya oleh pemegang view_cost (tambah MD). Sales melihat harga final saja dan mengajukan nego lewat harga khusus SO.
# UAT 24 Okt (P7) — menu Perbaikan.
for _role, _acts in {"admin": ["view", "create", "send", "receive", "cancel"], "manager": ["view", "create", "send", "receive", "cancel"],
                     "warehouse_admin": ["view", "create", "send", "receive", "cancel"], "md": ["view", "create", "send", "receive", "cancel"],
                     "warehouse": ["view", "send", "receive"], "finance": ["view"], "qc": ["view", "create"],
                     "md_quality": ["view", "create"]}.items():
    if _role in DEFAULT_PERMISSIONS:
        DEFAULT_PERMISSIONS[_role]["repair_order"] = list(_acts)
for _role, _acts in {"sales_admin": ["view_cost", "set_price", "lock"], "manager": ["view_cost", "set_price", "lock"],
                     "admin": ["view_cost", "set_price", "lock"], "md": ["view_cost"]}.items():
    if _role in DEFAULT_PERMISSIONS:
        DEFAULT_PERMISSIONS[_role]["od_pricing"] = list(_acts)
# L03 LN-034 — keputusan PIC atas uji ulang gagal & override eksplisit (terpisah dari ACC teknis/kontrak).
DEFAULT_PERMISSIONS["admin"]["rnd"] = list(DEFAULT_PERMISSIONS["admin"]["rnd"]) + ["pic_decide", "override_fail"]
# LN-015-T03 — ACC teknis per jenis uji; `assess`/`decide` umum tetap mencakup semua jenis.
RND_TYPED_ACTIONS = [f"{a}_{t}" for a in ("assess", "decide") for t in ("labdip", "handfeel", "proofing")]
DEFAULT_PERMISSIONS["admin"]["rnd"] = list(DEFAULT_PERMISSIONS["admin"]["rnd"]) + RND_TYPED_ACTIONS
DEFAULT_PERMISSIONS["manager"]["rnd"] = list(DEFAULT_PERMISSIONS["manager"]["rnd"]) + ["pic_decide", "override_fail"]
DEFAULT_PERMISSIONS["md"]["rnd"] = list(DEFAULT_PERMISSIONS["md"]["rnd"]) + ["pic_decide"]
# L11 LN-110/LN-113 — Pusat Export: lihat dataset/preview vs membuat & mengunduh file dipisah.
# Isi dataset tetap dijaga izin modul sumbernya, scope entitas/lokasi dan visibilitas field.
for _role in ("admin", "manager", "finance", "sales_admin", "sales", "md", "warehouse_admin", "designer"):
    DEFAULT_PERMISSIONS[_role]["data_export"] = ["view", "export"]
# FIX-4 (K-B4-07 · K-B3b-04) — petugas gudang boleh mengunduh daftar gudang (Excel/CSV). Isi dibatasi DAFTAR PUTIH
# dataset gudang di mesin export (`export_registry_wms.WAREHOUSE_ROLE_DATASETS`) + izin modul sumber + lokasi kerja.
DEFAULT_PERMISSIONS["warehouse"]["data_export"] = ["view", "export"]
# L09 LN-092 — cutloss: MD mencatat qty cacat saat QC; nilai cutloss/diskon diputus Finance (KLR-01/02/06/07).
for _role, _acts in {"admin": ["record_cutloss", "decide_compensation"], "manager": ["record_cutloss", "decide_compensation"],
                     "finance": ["decide_compensation"], "md": ["record_cutloss"], "md_quality": ["record_cutloss"]}.items():
    _cur = DEFAULT_PERMISSIONS[_role].setdefault("sales_return", ["view"])
    DEFAULT_PERMISSIONS[_role]["sales_return"] = list(_cur) + [x for x in _acts if x not in _cur]
# GL-01/GL-08 — Pemetaan Akun: Finance boleh mengubah tanpa persetujuan kedua (berlaku untuk jurnal baru).
for _role, _acts in {"admin": ["view", "update"], "finance": ["view", "update"], "manager": ["view"]}.items():
    DEFAULT_PERMISSIONS[_role]["gl_mapping"] = _acts
# GL-04 — Finance memilih akun pembayaran ongkir retur (kas/bank/hutang ekspedisi).
for _role in ("admin", "finance", "manager"):
    _cur = DEFAULT_PERMISSIONS[_role].setdefault("sales_return", ["view"])
    DEFAULT_PERMISSIONS[_role]["sales_return"] = list(_cur) + [x for x in ["post_logistics"] if x not in _cur]
# CUT-01/CUT-02 — proses pemecahan roll cutloss (siapa yang memilih BS/Dibuang diatur di Pusat Pengaturan).
for _role in ("admin", "manager", "md", "md_quality"):
    _cur = DEFAULT_PERMISSIONS[_role].setdefault("sales_return", ["view"])
    DEFAULT_PERMISSIONS[_role]["sales_return"] = list(_cur) + [x for x in ["split_cutloss"] if x not in _cur]
# Permintaan pemilik 23 Okt — terima/tolak PER ROLL retur (mis. tolak roll yang sudah dipotong). Bawaan Manajer,
# Admin & Admin Sales; dapat diberikan ke peran kustom lewat matriks akses.
for _role in ("admin", "manager", "sales_admin"):
    _cur = DEFAULT_PERMISSIONS[_role].setdefault("sales_return", ["view"])
    DEFAULT_PERMISSIONS[_role]["sales_return"] = list(_cur) + [x for x in ["decide_rolls"] if x not in _cur]
# … diteruskan ke retur ke SUPPLIER & retur ANTAR-PT: bawaan pemegang ACC-nya (Admin & Manajer), dapat diatur.
for _role in ("admin", "manager"):
    for _mod in ("purchase_return", "interco"):
        _cur = DEFAULT_PERMISSIONS[_role].setdefault(_mod, ["view"])
        DEFAULT_PERMISSIONS[_role][_mod] = list(_cur) + [x for x in ["decide_rolls"] if x not in _cur]
EXTRA_ACTIONS = {"sales_pov": ["commercial"]}
# Keputusan owner 2026-10-21 — nota kredit otomatis dari batal item Pesanan Khusus pada SO terbit: ditinjau
# (dikoreksi / diterbitkan / dibatalkan) pemegang izin ini; bawaan Finance, Manager, Admin — dapat diatur di matriks.
for _role in ("admin", "manager", "finance"):
    _cur = DEFAULT_PERMISSIONS[_role].setdefault("finance_amendment", [])
    DEFAULT_PERMISSIONS[_role]["finance_amendment"] = list(_cur) + [x for x in ("review_credit_note",) if x not in _cur]
# F-10 (keputusan owner Q-02, 2026-10-21) — pengecualian kirim untuk SO bertermin CBD/DP yang belum dibayar sesuai
# termin: alasan wajib & teraudit. Bawaan Finance, Manager, Admin — dapat diatur per peran di Peran & Hak Akses.
for _role in ("admin", "manager", "finance"):
    _cur = DEFAULT_PERMISSIONS[_role].setdefault("order", ["view"])
    DEFAULT_PERMISSIONS[_role]["order"] = list(_cur) + [x for x in ("release_unpaid",) if x not in _cur]
# PK-45 (K-28) — plafon & status blokir pelanggan hanya diubah pemegang `customer.manage_credit` (PUT
# /api/customers/{id}/credit; POST /api/customers tanpa izin ini menyimpan plafon 0). Sales TIDAK memegangnya.
# PK-45 (K-33) — pesanan penjualan tanpa PPN (`tax_override: "non_ppn"`) butuh `order.tax_override` + alasan.
# Bawaan dapat diatur per peran di Peran & Hak Akses; tersalin sekali ke matriks tersimpan (sync_permission_modules).
for _role, _pairs in {"admin": (("customer", "manage_credit"), ("order", "tax_override")),
                      "manager": (("customer", "manage_credit"), ("order", "tax_override")),
                      "finance": (("customer", "manage_credit"),)}.items():
    for _res, _act in _pairs:
        _cur = DEFAULT_PERMISSIONS[_role].setdefault(_res, ["view"])
        DEFAULT_PERMISSIONS[_role][_res] = list(_cur) + [x for x in (_act,) if x not in _cur]
# PK-38 (IA-12, K-17) — membayar hutang = pemegang izin bayar (bawaan Finance dan Manajer). Finance menerima
# `contra_bon` view + pay (BUKAN verify/approve): bayar kontrabon kini bisa dipegang orang yang berbeda dari
# penyetujunya. Tersalin sekali ke matriks tersimpan (sync_permission_modules); bisa dicabut di Peran & Hak Akses.
_cur = DEFAULT_PERMISSIONS["finance"].setdefault("contra_bon", [])
DEFAULT_PERMISSIONS["finance"]["contra_bon"] = list(_cur) + [x for x in ("view", "pay") if x not in _cur]
# PK-30 (IC-10) — harga per baris, mode harga, dan mode PPN antar-PT yang berbeda dari kontrak & pengaturan PT penjual
# hanya untuk pemegang `interco.override_terms` (+ alasan). Bawaan Admin & Manajer (pemegang `interco.approve`); Admin
# Sales yang dulu bisa mengetik harga sendiri kini butuh izin ini. Tersalin sekali ke matriks tersimpan
# (sync_permission_modules); dapat diatur di Peran & Hak Akses.
PK30_OVERRIDE_TERMS_ROLES = ("admin", "manager")
for _role in PK30_OVERRIDE_TERMS_ROLES:
    _cur = DEFAULT_PERMISSIONS[_role].setdefault("interco", ["view"])
    DEFAULT_PERMISSIONS[_role]["interco"] = list(_cur) + [x for x in ("override_terms",) if x not in _cur]

# ═══════════════════════════════════════════════════════════════════════════
# PR-T2 (K-47) — wewenang yang dulu ditentukan NAMA PERAN (`require_role`, daftar peran di handler) kini izin biasa:
# tampil dan bisa dicabut di layar Peran & Hak Akses, dan bisa diberikan ke peran kustom tanpa peran acuan.
# Penerima bawaan = siapa yang hari ini lolos lewat nama peran (tabel "Izin dan peran", docs/blueprint/unit/PR-T2.md).
# Instalasi lama menerima pasangan ini sekali lewat `bootstrap.migrate_role_gates_to_permissions`.
# ═══════════════════════════════════════════════════════════════════════════
_PRT2_AI_VIEW = ("admin", "manager", "sales_admin", "finance", "md", "warehouse_admin", "sales")   # = ai.enabled_roles bawaan
PRT2_RESOURCES = {
    "sales_force": {"admin": ["view", "update", "delete", "post", "assign"],
                    "manager": ["view", "update", "delete", "post", "assign"]},
    "credit_override": {"admin": ["approve"], "manager": ["approve"]},
    "costing": {"admin": ["view"], "manager": ["view"]},
    "manager_home": {"admin": ["view"], "manager": ["view"]},
    "system_tools": {"admin": ["view", "update", "configure"], "manager": ["view", "update"]},
    "rfid_device": {"admin": ["configure", "revoke"], "warehouse_admin": ["revoke"]},
    "ai": {r: (["view"] + (["view_margin"] if r in ("admin", "manager") else [])
               + (["view_stock_value"] if r in ("admin", "manager", "finance") else [])
               + (["manage"] if r in ("admin", "manager") else []) + (["configure"] if r == "admin" else []))
           for r in _PRT2_AI_VIEW},
}
#: Aksi baru pada sumber daya lama → peran penerima bawaan.
PRT2_ACTIONS = {
    ("rnd", "manage_org"): ("admin", "manager"), ("rnd", "report"): ("admin", "manager"),
    ("rnd", "extend_rounds"): ("admin", "manager"),
    ("goods_receipt", "configure"): ("admin", "manager"),   # sudah ada sejak KF-T1 (mode surat jalan supplier)
    ("warehouse", "configure"): ("admin", "warehouse_admin"),
    ("accounting", "reopen"): ("admin",),
    ("inspection", "release"): ("admin", "manager"),
    ("product", "retire"): ("admin", "md"),
    ("sales_return", "treat_cutloss"): ("admin", "manager", "md", "md_quality"),
    ("od_pricing", "unlock"): ("admin",),
}
for _res, _by_role in PRT2_RESOURCES.items():
    for _role, _acts in _by_role.items():
        DEFAULT_PERMISSIONS[_role][_res] = list(_acts)
for (_res, _act), _roles in PRT2_ACTIONS.items():
    for _role in _roles:
        _cur = list(DEFAULT_PERMISSIONS[_role].get(_res) or [])
        DEFAULT_PERMISSIONS[_role][_res] = _cur + [_act] if _act not in _cur else _cur
# Templat laporan Tanya KN: satu aksi per templat (id templat). Sumber nilai bawaan = field `roles` di JSON templat;
# hanya peran yang bisa membuka asisten (`ai.view`) yang menerimanya. Admin: semua templat.
import json as _json  # noqa: E402 — dipakai blok PR-T2 saja
from pathlib import Path as _Path  # noqa: E402

AI_TEMPLATES = _json.loads((_Path(__file__).resolve().parent / "data" / "ai" / "templates_laporan_v1.json")
                           .read_text(encoding="utf-8"))["templates"]
AI_TEMPLATE_IDS = [t["id"] for t in AI_TEMPLATES]
DEFAULT_PERMISSIONS["admin"]["ai_template"] = list(AI_TEMPLATE_IDS)
for _role, _mods in DEFAULT_PERMISSIONS.items():
    if _role != "admin" and "view" in (_mods.get("ai") or []):
        _ids = [t["id"] for t in AI_TEMPLATES if _role in (t.get("roles") or [])]
        if _ids:
            _mods["ai_template"] = _ids

# ═══════════════════════════════════════════════════════════════════════════
# PR-T4 — melihat KPI & komisi sales LAIN (`routers/crm._kpi_scope`): dulu daftar nama peran admin/manajer/admin
# sales/finance, kini izin `order.view_sales_kpi` (modul Pesanan Penjualan). Instalasi lama menerimanya sekali lewat
# `custom_role_service.migrate_kpi_permission` (`prt4:izin-kpi-sales`) — juga peran kustom berdasar keempatnya.
# ═══════════════════════════════════════════════════════════════════════════
PRT4_KPI_ROLES = ("admin", "manager", "sales_admin", "finance")
for _role in PRT4_KPI_ROLES:
    _cur = list(DEFAULT_PERMISSIONS[_role].get("order") or [])
    DEFAULT_PERMISSIONS[_role]["order"] = _cur + [x for x in ("view_sales_kpi",) if x not in _cur]

# ═══════════════════════════════════════════════════════════════════════════
# PR-T5 (PR-07) — pasangan izin yang TIDAK diperiksa server di mana pun (tidak ada pemeriksa literal maupun dinamis) dan
# tidak dipakai layar untuk keputusan yang ditegakkan server: dihapus dari katalog supaya setiap tombol izin di layar
# peran berakibat nyata (`docs/blueprint/unit/PR-T5.md` tabel 1). Cetak dijaga `document.print`, unduhan dijaga
# `data_export.export`, ubah transaksi antar-PT dijaga `interco.create`, tombol "Tambah Stok" memakai `product.create`
# (izin yang memang diperiksa `POST /api/inventory/initial-stock`). Matriks tersimpan dibersihkan sekali lewat migrasi
# `prt5:katalog` (`services/custom_role_service.migrate_prt5_catalog`). Penjaga: `scripts/guardrails/
# verify_permission_checked.py` (INV-PERM-01) — pasangan baru wajib punya pemeriksa.
# ═══════════════════════════════════════════════════════════════════════════
PRT5_REMOVED_PAIRS = (
    ("esign", "manage"), ("finance_case", "admin"), ("interco", "update"), ("inventory", "create"),
    ("order", "print"), ("tax_invoice", "print"), ("template", "print"),
    ("template", "import"), ("template", "export"), ("uom", "import"), ("uom", "export"),
    ("transfer", "complete"), ("reports", "export"), ("sales_pov", "commercial"),
)
#: Sumber daya yang dihapus seluruhnya (modul "Profil POV Sales Komersial" tidak pernah dibaca kode mana pun).
PRT5_REMOVED_RESOURCES = ("sales_pov",)
for _mods in DEFAULT_PERMISSIONS.values():
    for _res, _act in PRT5_REMOVED_PAIRS:
        if _act in (_mods.get(_res) or []):
            _mods[_res] = [a for a in _mods[_res] if a != _act]
            if not _mods[_res]:
                del _mods[_res]
    for _res in PRT5_REMOVED_RESOURCES:
        _mods.pop(_res, None)
for _res in PRT5_REMOVED_RESOURCES:
    EXTRA_ACTIONS.pop(_res, None)

# ═══════════════════════════════════════════════════════════════════════════
# MN-T1 (K-09, K-17) — izin bawaan peran Finance untuk menu Keuangan yang baru (docs/blueprint/unit/MN-T1.md, tabel
# "Izin bawaan peran Finance"). HANYA MENAMBAH: Hutang dilihat dan dibayar oleh pemegang izin bayar (bawaan Finance dan
# Manajer, K-17), mencairkan uang muka juga Finance dan Manajer (K-17; dulu hanya Admin). Rekonsiliasi Bank (K-09: ya —
# `cash.view/create`) dan Buku Besar lihat saja (K-09 — `accounting.view`) sudah dipegang. Instalasi lama menerima
# pasangan baru sekali lewat `bootstrap.sync_permission_modules` (`defaults_applied`, PR-T9); pencabutan Admin sesudahnya
# bertahan. PK-24/PK-38 memuat baris yang sama ("lewati bila sudah ada") — blok ini idempoten.
# ═══════════════════════════════════════════════════════════════════════════
MNT1_DEFAULT_PAIRS = {
    "finance": {"vendor_bill": ("view", "pay"), "contra_bon": ("view", "pay"), "cash_advance": ("disburse",)},
    "manager": {"cash_advance": ("disburse",)},
}
for _role, _mods in MNT1_DEFAULT_PAIRS.items():
    for _res, _acts in _mods.items():
        _cur = list(DEFAULT_PERMISSIONS[_role].get(_res) or [])
        if "view" in _acts and "view" not in _cur:
            _cur.insert(0, "view")
        DEFAULT_PERMISSIONS[_role][_res] = _cur + [a for a in _acts if a not in _cur]

# ═══════════════════════════════════════════════════════════════════════════
# KP-T8 (KP-32, K-47) — kunci integrasi dijaga izinnya sendiri `integration.manage` (dulu `hr.manage_settings`, yang juga
# menjaga pengaturan SDM). Bawaan: Admin — satu-satunya peran bawaan pemegang `hr.manage_settings`, jadi tidak ada yang
# kehilangan akses. Instalasi lama menerima pasangan ini sekali lewat `bootstrap.sync_permission_modules`
# (`defaults_applied`, PR-T9); peran kustom/bawaan lain yang memegang `hr.manage_settings` diberi `integration.manage`
# oleh `scripts/migrate_kpt8_rahasia.py` (dijalankan pemilik — H3).
# ═══════════════════════════════════════════════════════════════════════════
KPT8_DEFAULT_PAIRS = {"admin": {"integration": ("manage",)}}
for _role, _mods in KPT8_DEFAULT_PAIRS.items():
    for _res, _acts in _mods.items():
        _cur = list(DEFAULT_PERMISSIONS[_role].get(_res) or [])
        DEFAULT_PERMISSIONS[_role][_res] = _cur + [a for a in _acts if a not in _cur]
