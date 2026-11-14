"""KATALOG MODUL HAK AKSES — bahasa manusia di atas matriks izin teknis.

Satu "modul" = kelompok sumber daya izin (`permissions_config`) + menu/tab yang
membukanya. Admin mengatur per modul dengan 3 tingkat: none · view · manage ("Tidak ada" · "Lihat saja" · "Semua aksi");
tingkat yang tidak berlaku untuk sebuah modul tidak ditawarkan (`levels_available`, PR-T5). Aksi berisiko diberi kalimat
akibat per aksi (`SENSITIVE_ACTIONS`). Label sumber daya & aksi di sini adalah SATU kamus untuk editor peran, pesan
penolakan, dan jejak audit (`GET /api/access/labels`).
"""
from typing import Any, Dict, List, Tuple

from permissions_config import AI_TEMPLATES, DEFAULT_PERMISSIONS, EXTRA_ACTIONS

LEVELS = ("none", "view", "manage")
LEVEL_LABEL = {"none": "Tidak ada", "view": "Lihat saja", "manage": "Semua aksi"}   # PR-T5 — dulu "Kelola penuh"

#: Menu yang selalu terlihat oleh peran kustom apa pun.
ALWAYS_NAV = ["hr-my-profile"]

MODULE_CATALOG: List[Dict[str, Any]] = [
    {"id": "penjualan", "group": "Penjualan", "label": "Pesanan Penjualan",
     "description": "Pesanan (SO), koreksi, retur, pesanan khusus, dan permintaan internal antar badan usaha.",
     "resources": ["order", "sales_return", "internal_request", "od_fulfillment", "od_pricing"],
     "nav": ["penjualan", "sales", "sales-orders", "orders", "amendments", "returns", "returns-hub",
             "return-policies", "special-orders", "internal-requests", "keep-pending",
             # Fase 3 · P8 (P16-K1) — Pengaturan kini GRUP: Kebijakan Retur di Pengaturan › Penjualan (+ aturannya).
             "settings-hub", "settings-sales", "settings-cfg-sales"]},
    {"id": "sample_order", "group": "Penjualan", "label": "Pesanan Sample",
     "description": "Pesanan sample (SOS) yang terpisah dari pesanan roll biasa.",
     "resources": ["sample_order"], "nav": ["penjualan", "sample-orders"]},
    {"id": "customer", "group": "Penjualan", "label": "Pelanggan & CRM",
     "description": "Data pelanggan, riwayat, dan kunjungan sales.",
     "resources": ["customer"], "nav": ["penjualan", "customers-crm", "hr-visits"]},
    {"id": "product", "group": "Penjualan", "label": "Produk, Kategori & Satuan",
     "description": "Master produk & varian, kategori, pustaka warna, satuan, dan template dokumen.",
     "resources": ["product", "uom", "color", "template"],
     "nav": ["penjualan", "products-pricing", "md-products", "product-templates", "client-dataset-import",
             "md-categories", "color-library", "md-uoms",
             # Fase 3 · P8 (P16-K1) — Koreksi Harga (dulu tab Pusat Pengaturan): server pratinjau product.view,
             # terapkan product.update — karena itu modul Produk (bukan Harga).
             "price-corrections"]},
    {"id": "pricing", "group": "Penjualan", "label": "Harga & Persetujuan Harga",
     "description": "Daftar harga per badan usaha, harga per pelanggan, dan persetujuan harga khusus.",
     "resources": ["pricelist", "price_approval"],
     "nav": ["penjualan", "products-pricing", "pricelist", "cs-price-list",
             "approval-inbox", "price-approvals",
             "settings-hub", "settings-sales", "settings-cfg-sales"]},   # fase 3 · P8 — aturan harga & diskon
    {"id": "purchasing", "group": "Pembelian", "label": "Pembelian & Pengadaan",
     "description": "Permintaan pembelian (PR), RFQ, pesanan pembelian (PO), dan retur pembelian.",
     "resources": ["purchase_order", "purchase_requisition", "rfq", "purchase_return"],
     "nav": ["pembelian", "sourcing", "reorder", "purchase-requisitions", "rfq",
             "purchase-orders", "purchasing", "po-board", "blanket-po",
             "approval-inbox", "purchase-approval", "purchase-returns", "returns-hub",   # FE-03: tab Hutang milik modul payable
             "settings-hub", "settings-purchasing", "settings-cfg-purchasing"]},   # fase 3 · P8 — Pengaturan › Pembelian
    {"id": "supplier", "group": "Pembelian", "label": "Pemasok & Makloon",
     "description": "Master pemasok, mitra makloon, kontrak, barang supplier, resep proses & order makloon.",
     "resources": ["supplier", "supplier_contract", "supplier_item", "makloon",
                   "makloon_order", "process_recipe"],
     "nav": ["pembelian", "master-pembelian", "suppliers", "makloons", "supplier-contracts",
             "supplier-items", "process-recipes", "purchase-orders", "makloon-orders", "makloon-claim-recap",
             "makloon-claims",
             # Fase 3 · P8 (D-23) — Harga Internal dari Kontrak (tab tersembunyi Master Pembelian; tulis = interco_price).
             "supplier-internal-prices",
             "settings-hub", "settings-purchasing", "settings-cfg-purchasing"]},
    {"id": "payable", "group": "Pembelian", "label": "Hutang Supplier & Kontrabon",
     "description": "Tagihan supplier, kontrabon (tukar faktur), landed cost, dan faktur pajak masukan.",
     "resources": ["vendor_bill", "contra_bon", "landed_cost", "input_tax"],
     "nav": ["pembelian", "accounts-payable", "vendor-bills", "contra-bons", "landed-cost",
             "keuangan", "akuntansi", "tax-hub", "input-tax",   # fase 3 · P8: Pajak ada di grup Akuntansi & Pajak
             "settings-hub", "settings-purchasing", "settings-cfg-purchasing"]},   # fase 3 · P8 — aturan kontrabon
    {"id": "interco", "group": "Pembelian", "label": "Transaksi Antar Badan Usaha",
     "description": "Jual-beli antar PT dalam grup, settlement, dan saldo pasangan PT.",
     "resources": ["interco", "interco_finance", "interco_price"],
     "nav": ["pembelian", "interco-transactions", "interco-returns", "returns-hub",   # FE-03: tab Hutang milik modul payable
             "akuntansi",   # fase 3 · P8 — induk Antar Entitas (Grup) ikut katalog, palet/deep link peran kustom sah
             "supplier-internal-prices"]},   # fase 3 · P8 (D-23) — Harga Internal Antar-PT dari Kontrak
    {"id": "rnd", "group": "Produk & Desain", "label": "Riset & Sample (R&D)",
     "description": "Spesifikasi produk, permintaan sample, labdip, handfeel, proofing, dan laporan R&D.",
     "resources": ["rnd"],
     # Fase 3 · P8 (D-24b) — `rnd-labdip` dkk. kini alias ke `rnd-samples` (chip jenis); id lama TETAP di sini: dikenal
     # rute cadangan, sah sebagai `hidden_views` (menyembunyikan chip jenisnya), dan dipakai `canOpen` layar.
     "nav": ["rnd-hub", "rnd-specs", "rnd-samples", "rnd-revalidation", "rnd-labdip", "rnd-handfeel",
             "rnd-proofing", "rnd-reports",
             "settings-hub", "settings-rnd", "settings-cfg-rnd"]},
    {"id": "design", "group": "Produk & Desain", "label": "Desain & Desainer",
     "description": "Permintaan desain, galeri desain & pattern, KPI desainer.",
     "resources": ["design_request", "design_ownership"],
     "nav": ["designer-hub", "design-requests", "designer-kpi", "rnd-designs",
             "cs-design-gallery", "rnd-divisions",   # fase 3 · P8 (D-09) — cs-design-gallery = alias mode Galeri
             # Pengaturan › Persetujuan (Divisi & Persetujuan R&D) + Pengaturan › R&D (aturan & penempatan tim).
             "settings-hub", "settings-approval", "settings-rnd", "settings-cfg-rnd"]},
    {"id": "marketing", "group": "Penjualan", "label": "Marketing & Sosial Media",
     "description": "Kalender konten, kampanye, persetujuan konten, performa post.",
     "resources": ["marketing"],
     "nav": ["marketing-hub", "mkt-calendar", "mkt-campaigns", "mkt-analytics", "mkt-accounts"]},
    {"id": "warehouse_ops", "group": "Gudang", "label": "Operasi Gudang (WMS)",
     "description": "Barang masuk/keluar, lokasi rak, data gudang, label, produksi in-house, RFID.",
     "resources": ["wms", "goods_receipt", "warehouse", "label", "production", "repair_order"],
     # FE-03 — tab Barang Masuk/Keluar & hub RFID ikut modul ini (dulu `rfid` = ID tak dikenal menu).
     "nav": ["gudang", "wms-operations", "operations", "goods-receipts", "wms-outbound", "wms-cutting", "repair-orders",
             "quality-hub", "qc-inspection",
             "wms-locations", "md-warehouses", "production", "escalations", "rfid-hub", "cs-rfid-lokasi",
             "cs-rfid-tags", "cs-rfid-devices", "cs-rfid-gate",
             # F-11-layar — retur pelanggan yang menunggu scan terima/kirim/tiba (tampilan tanpa uang)
             "returns-hub", "returns",
             # Fase 3 · P8 (D-29) — Perangkat RFID kini tab di Pengaturan › Integrasi & Sistem › Perangkat
             # (`cs-rfid-devices` = alias); aturan gudang di Pengaturan › Gudang & Mutu.
             "settings-hub", "settings-warehouse", "settings-cfg-warehouse", "settings-system", "settings-devices"]},
    {"id": "inventory", "group": "Gudang", "label": "Stok & Persediaan",
     "description": "Status stok & ATP, lot & silsilah, stock opname, transfer antar gudang/entitas.",
     "resources": ["inventory", "transfer"],
     "nav": ["gudang", "stock-atp", "inventory-board", "stock-buckets", "inventory-lots",
             "wms-operations", "operations", "interco-transfers", "cs-stock-analytics",   # FE-03 · P8 (D-16): interco-transfers = alias Transfer "Antar PT"
             # Fase 3 · P8 — induk hub Analitik ikut modul yang memuat tab Analitik Stok: tanpa ini `analytics` hanya
             # milik modul Laporan dan Admin Gudang (izin inventory, tanpa reports) terblokir dari Analitik Stok.
             "analytics",
             # KF-T1 — kunci `lot.*` kini diubah lewat `inventory.configure`: tab Aturan Gudang & Mutu ikut modul ini
             # (isi tab disaring server; tanpa izin baca/ubah tab menampilkan pesan, bukan galat).
             "settings-hub", "settings-warehouse", "settings-cfg-warehouse"]},
    {"id": "inspection", "group": "Kualitas", "label": "Inspeksi & QC",
     "description": "SPK inspeksi, hasil pemeriksaan warna/handfeel, keputusan terima/tolak.",
     "resources": ["inspection"],
     "nav": ["quality-hub", "inspections", "qc-inspection",   # 23 Okt — menu Kualitas
             "settings-hub", "settings-warehouse", "settings-cfg-warehouse"]},   # fase 3 · P8 — aturan kualitas & lot
    {"id": "md_quality", "group": "Kualitas", "label": "MD Quality",
     "description": "Warna & handfeel vs sample ACC (penerimaan PO & hasil makloon), lepas/tolak tahanan.",
     "resources": ["md_quality"],
     "nav": ["quality-hub", "qc-inspection", "inspections"]},   # 23 Okt — menu Kualitas
    {"id": "qc", "group": "Kualitas", "label": "QC (4-point & random check)",
     "description": "Cacat 4-point & grade per roll, random check roll di stok.",
     "resources": ["qc"],
     # F-11-layar — retur pelanggan yang menunggu/menjalani QC (tampilan tanpa uang)
     "nav": ["quality-hub", "qc-inspection", "inspections", "returns-hub", "returns"]},   # 23 Okt — menu Kualitas
    {"id": "logistics", "group": "Gudang", "label": "Pengiriman & Kendaraan",
     "description": "Pengiriman (ekspedisi/armada), foto muat & POD, log kendaraan.",
     "resources": ["logistics", "vehicle_log"],
     "nav": ["gudang", "logistics", "kas-aset", "vehicle-logs"]},
    {"id": "ar", "group": "Keuangan", "label": "Uang Masuk, Piutang & Faktur Pajak",
     "description": "Kwitansi AR, piutang, rencana bayar, denda, selisih bayar, faktur pajak keluaran.",
     "resources": ["ar_receipt", "tax_invoice", "payment_plan", "penalty", "payment_variance"],
     "nav": ["keuangan", "ar-aging", "advance-report", "payment-plans", "store-credit",
             "akuntansi", "tax-hub", "tax-invoices", "cs-pajak",   # fase 3 · P8: Pajak ada di grup Akuntansi & Pajak
             "settings-hub", "settings-finance", "settings-cfg-finance"]},   # fase 3 · P8 — aturan piutang & pajak
    {"id": "finance_ops", "group": "Keuangan", "label": "Kas, Bank & Kasus Keuangan",
     "description": "Dasbor keuangan, rekening & saldo, transaksi kas, rekonsiliasi bank, kasus uang nyangkut, amandemen.",
     # PK-17 — `cash.configure` (kelola rekening kas & bank, menu `bank-accounts`) ikut tingkat "Kelola penuh"
     # (aksi penuh = aksi Admin di DEFAULT_PERMISSIONS).
     "resources": ["cash", "finance_case", "finance_amendment"],
     "nav": ["keuangan", "finance-tower", "cash-bank", "bank-accounts", "cash-management",
             "bank-reconciliation", "finance-cases",
             "settings-hub", "settings-finance", "settings-cfg-finance"]},   # fase 3 · P8 — aturan bank & periode
    {"id": "accounting", "group": "Keuangan", "label": "Akuntansi & Tutup Buku",
     "description": "Buku besar, laporan keuangan, anggaran, aset tetap, tutup buku & buka periode.",
     "resources": ["accounting", "period", "budget", "fixed_asset", "gl_mapping"],
     "nav": ["keuangan", "akuntansi", "ledger", "general-ledger", "chart-of-accounts", "gl-account-mappings", "fin-reports",
             "financial-statements", "profitability", "cashflow-forecast", "budget",
             "consolidation", "closing", "period-unlock", "posting-failures", "kas-aset", "fixed-assets",
             # Fase 3 · P8 (P16-K1) — Pemetaan Akun kini di Pengaturan › Keuangan & Pajak.
             "settings-hub", "settings-finance", "settings-cfg-finance"]},
    {"id": "petty_cash", "group": "Keuangan", "label": "Kas Kecil (PD / LPJ)",
     "description": "Pengajuan dana, pertanggungjawaban, kategori beban.",
     "resources": ["cash_advance", "cash_settlement"],
     "nav": ["kas-aset", "petty-cash", "cash-advances", "settlements", "expense-categories",
             # Fase 3 · P8 (D-02) — Kategori Beban kini di Pengaturan › Keuangan & Pajak.
             "settings-hub", "settings-finance", "settings-cfg-finance"]},
    {"id": "hr", "group": "Organisasi", "label": "SDM & Penggajian",
     "description": "Karyawan, struktur organisasi, presensi, cuti, lembur, payroll, KPI.",
     "resources": ["hr"],
     "nav": ["hrd", "hr-people", "hr-employees", "hr-org-units", "hr-attendance-hub",
             "hr-attendance", "hr-leave", "hr-overtime", "hr-live-tracking",
             "hr-attendance-setup", "hr-payroll-hub", "hr-payroll-runs", "hr-payslips",
             "hr-kpi-hub", "cs-kpi",
             # Fase 3 · P8 (P16-K1, D-29) — Shift & Geofence + aturan SDM di Pengaturan › SDM; mesin absen di
             # Pengaturan › Integrasi & Sistem › Perangkat (tab Mesin absen).
             "settings-hub", "settings-hr", "settings-cfg-hr", "settings-system", "settings-devices"]},
    {"id": "documents", "group": "Alat", "label": "Dokumen, Cetak & Tanda Tangan",
     "description": "Pusat dokumen, jejak dokumen, pusat cetak, e-sign, pengiriman dokumen.",
     "resources": ["document", "esign", "document_delivery", "pdf_template"],
     "nav": ["document-center", "doc-trace", "documents"]},
    {"id": "reports", "group": "Alat", "label": "Laporan & Analitik",
     "description": "Dasbor analitik, margin & HPP, BI keuangan/SDM, jejak audit.",
     "resources": ["reports", "audit"],
     "nav": ["analytics", "reports", "costing", "bi-finance", "cs-bi-hrd",   # FE-03: cs-bi-sales/stock tidak ada lagi di menu
             # Fase 3 · P8 (D-11) — Margin & HPP (`costing`, kini alias) = tab "Margin katalog" di Akuntansi & Pajak ›
             # Laporan › Profitabilitas & Margin. Tab Realisasi tetap dijaga izin akuntansi (server + layar).
             # `akuntansi` (id grup) WAJIB ikut: palet Ctrl+K / deep link / `canOpen` hanya menelusuri grup yang terlihat
             # menurut katalog — tanpa itu alias `costing` buntu untuk peran kustom bermodul Laporan.
             "akuntansi", "fin-reports", "profitability"]},
    {"id": "data_export", "group": "Alat", "label": "Pusat Export Data",
     "description": "Memilih dataset, kolom, filter & periode lalu mengunduh XLSX/CSV. Isi tetap dibatasi izin modul "
                    "sumber, badan usaha/lokasi, dan visibilitas field (grade/LOT/HPP).",
     "resources": ["data_export"], "nav": ["export-center"]},
    {"id": "approval", "group": "Alat", "label": "Pusat Persetujuan",
     "description": "Melihat antrean persetujuan lintas modul. Keputusan tetap dijaga izin dokumennya.",
     "resources": ["approval"], "nav": ["approval-inbox", "my-approvals"]},
    {"id": "grade_master", "group": "Produk & Desain", "label": "Master Grade Mutu",
     "description": "Daftar grade & urutan mutu (rank). Tambah, ubah, aktif/nonaktif dipisah; grade nonaktif "
                    "tidak bisa dipakai input baru di semua form, histori tetap terbaca.",
     "resources": ["grade_master"],
     "nav": ["grade-master", "settings-hub", "settings-warehouse"]},   # fase 3 · P8 — Pengaturan › Gudang & Mutu
    # PR-T5 — modul sakelar (Mati/Nyala); pindah ke grup Gudang. Modul "Profil POV Sales Komersial" (`sales_pov`) dihapus:
    # tidak dibaca kode mana pun (`services/field_visibility.hidden_for` sengaja mengabaikannya).
    {"id": "field_visibility", "group": "Gudang", "label": "Melihat grade, nomor lot & asal barang",
     "description": "Boleh melihat grade, LOT (internal/supplier/dye lot) dan asal lokal/impor di layar, API, detail, "
                    "ekspor dan dokumen cetak. Tanpa izin ini atribut disembunyikan server.",
     "resources": ["field_visibility"], "nav": []},
    # PR-T2 (K-47) — wewenang yang dulu ditentukan nama peran kini modul akses yang terlihat & bisa dicabut.
    {"id": "sales_force", "group": "Penjualan", "label": "Pengawasan Tim Sales & Kredit",
     "description": "Target & insentif sales, tarif komisi, penugasan ulang pelanggan, akrual insentif ke buku besar, "
                    "dan persetujuan pengecualian batas kredit.",
     "resources": ["sales_force", "credit_override"],
     "nav": ["settings-hub", "settings-sales", "incentive-rates"]},
    {"id": "costing", "group": "Alat", "label": "HPP & Margin Produk",
     "description": "Harga pokok rata-rata (HPP) per produk dan kolom biaya/margin di layar lain. Tanpa izin ini kolom "
                    "biaya disembunyikan server.",
     "resources": ["costing"], "nav": ["costing", "akuntansi", "fin-reports", "profitability"], "sensitive": True},
    {"id": "manager_home", "group": "Alat", "label": "Beranda Manajer",
     "description": "Ringkasan beranda manajer & admin (angka penjualan, stok, dan antrean lintas modul).",
     "resources": ["manager_home"], "nav": []},
    {"id": "system_tools", "group": "Organisasi", "label": "Kebersihan Data & Alat Sistem",
     "description": "Riwayat & pratinjau kebersihan data, perbaikan lokasi, peta notifikasi giliran; 'Kelola penuh' juga "
                    "menjalankan/mengembalikan pembersihan dan melepas kunci proses yang macet.",
     "resources": ["system_tools"], "nav": [], "sensitive": True},
    {"id": "devices", "group": "Gudang", "label": "Perangkat RFID & Handheld",
     "description": "Mendaftarkan dan mengatur reader RFID, printer label, dan handheld (kunci API, profil, parameter "
                    "gerbang), serta mencabut akses perangkat yang hilang.",
     "resources": ["rfid_device"], "nav": ["settings-hub", "settings-system", "settings-devices"], "sensitive": True},
    {"id": "assistant", "group": "Alat", "label": "Asisten Tanya KN",
     "description": "Asisten analitik: chat, templat laporan (per templat), jadwal laporan; margin & nilai persediaan "
                    "dipisah; pemakaian & biaya asisten.",
     "resources": ["ai", "ai_template"], "nav": ["tanya-kn"]},
    # PR-T5 (PR-08) — modul "Pengaturan, Pengguna & Hak Akses" (`admin`) DIPECAH lima: memberi "kelola akun" tidak lagi
    # ikut memberi "ubah peran", "kelola PT", "ubah pengaturan", dan "penjadwal". Id lama `admin` tetap diterima sebagai
    # alias kelimanya (`MODULE_ALIASES`). `pdf-templates`/`settings-documents` pindah ke modul Dokumen (pemilik
    # `pdf_template`); `settings-devices` tetap milik Operasi Gudang, SDM, dan Perangkat (PR-T2).
    {"id": "accounts", "group": "Organisasi", "label": "Akun Pengguna",
     "description": "Membuat, mengubah, menonaktifkan akun dan mereset sandi.",
     "resources": ["user"], "nav": ["settings-hub", "settings-company", "entities-access"], "sensitive": True},
    {"id": "roles", "group": "Organisasi", "label": "Peran & Hak Akses",
     "description": "Mengatur hak akses peran. Hati-hati: bisa mengubah hak akses orang lain.",
     "resources": ["permission"], "nav": ["settings-hub", "settings-company", "entities-access"], "sensitive": True},
    {"id": "entities", "group": "Organisasi", "label": "Badan Usaha (PT)",
     "description": "Data PT dalam grup (identitas, pajak, kode dokumen), master per PT, dan pengarsipan PT.",
     "resources": ["entity"],
     "nav": ["settings-hub", "settings-company", "entities-access", "settings-masters", "entity-masters"],
     "sensitive": True},
    {"id": "settings", "group": "Organisasi", "label": "Pusat Pengaturan",
     "description": "Aturan sistem yang dipakai mesin: persetujuan, master domain, dokumen, notifikasi, dan integrasi.",
     "resources": ["settings"],
     "nav": ["settings-hub", "settings-system", "settings-config", "settings-cfg-system", "admin",
             "settings-approval", "approval-rules", "settings-cfg-approval", "settings-masters", "domain-registry",
             "settings-cfg-documents", "settings-notify", "settings-cfg-notify",
             # Induk tab `settings-cfg-documents` (hubTabs "settings-documents"): tanpa ini tab dokumen Pusat Pengaturan
             # tidak terjangkau pemegang modul ini. Grup yang sama juga milik modul Dokumen (tab Template Dokumen).
             "settings-documents"],
     "sensitive": True},
    {"id": "scheduler", "group": "Organisasi", "label": "Penjadwal & Notifikasi Otomatis",
     "description": "Jadwal tugas otomatis (pengingat, ringkasan, sinkronisasi) dan saluran notifikasi otomatisnya.",
     "resources": ["scheduler"], "nav": ["settings-hub", "settings-notify", "scheduler"]},
]

# KF-T6 — tab Pengaturan › Persetujuan › Kontrol dua orang ikut modul Pusat Pengaturan (PR-T5: dulu modul `admin`).
next(m for m in MODULE_CATALOG if m["id"] == "settings")["nav"].append("settings-dual-control")

# ─── PR-T5 — menu/tab di luar katalog (lampiran B C.2) masuk modul pemilik datanya ─────────────────────────────────
# Meja peran + grup `meja-peran` ikut modul alur kerjanya (menu baru tampil hanya bila syarat aksi
# `VIEW_ACTION_REQUIREMENTS` terpenuhi). `home` dan `my-desk` tidak masuk modul: menurut sifat peran
# (`role_registry.apply_traits`). `permission-matrix` (alias), `cs-bom` (segera hadir), `hr-my-profile` tidak berubah.
_PRT5_NAV = {
    "penjualan": ["sales-admin-desk", "meja-peran"],
    "ar": ["finance-desk", "meja-peran"],
    "design": ["md-desk", "meja-peran"],
    "warehouse_ops": ["warehouse-admin-desk", "meja-peran", "settings-receiving-ocr"],
    "sample_order": ["sample-admin-desk", "meja-peran"],
    "customer": ["customers-master"],
    "interco": ["internal-prices"],
    "petty_cash": ["reimburse-payables"],
    "finance_ops": ["amendment-reasons", "bank-recon-rules"],
    "documents": ["pdf-templates", "settings-documents"],
}
for _m in MODULE_CATALOG:
    _m["nav"].extend(v for v in _PRT5_NAV.get(_m["id"], []) if v not in _m["nav"])

MODULE_BY_ID = {m["id"]: m for m in MODULE_CATALOG}
#: PR-T5 — id modul lama → id modul penggantinya. `apply_levels`/`nav_for_levels` menerima id lama (permintaan, uji, dan
#: `custom_roles.levels` lama); jawaban selalu memakai id baru.
MODULE_ALIASES: Dict[str, List[str]] = {"admin": ["accounts", "roles", "entities", "settings", "scheduler"]}
_ADMIN = DEFAULT_PERMISSIONS["admin"]


def full_actions(resource: str) -> List[str]:
    return list(_ADMIN.get(resource, [])) or list(EXTRA_ACTIONS.get(resource, []))


def _held_total(perms: Dict[str, List[str]], mod: Dict[str, Any]) -> Tuple[int, int]:
    """PR-T5 — (aksi dipegang, aksi penuh) sebuah modul; "*" = semua aksi sumber daya itu."""
    held = total = 0
    for r in mod["resources"]:
        full = full_actions(r)
        have = set(perms.get(r, []) or [])
        total += len(full)
        held += len(full) if "*" in have else len(have & set(full))
    return held, total


def level_of(perms: Dict[str, List[str]], module_id: str) -> Dict[str, Any]:
    """Tingkat efektif sebuah modul dari daftar aksi mentah. PR-T5: + `held`/`total` (jumlah aksi dipegang / penuh)
    supaya layar menulis "Sebagian (7 dari 13 aksi)" alih-alih "Kelola penuh · sebagian"."""
    mod = MODULE_BY_ID[module_id]
    held, total = _held_total(perms, mod)
    acts = set()
    for r in mod["resources"]:
        acts.update(perms.get(r, []) or [])
    if not acts:
        return {"level": "none", "partial": False, "held": 0, "total": total}
    if acts <= {"view"}:
        return {"level": "view", "partial": False, "held": held, "total": total}
    full = all(set(perms.get(r, []) or []) >= set(full_actions(r)) for r in mod["resources"])
    return {"level": "manage", "partial": not full, "held": held, "total": total}


def levels_of(perms: Dict[str, List[str]]) -> Dict[str, Dict[str, Any]]:
    return {m["id"]: level_of(perms, m["id"]) for m in MODULE_CATALOG}


def expand_aliases(levels: Dict[str, Any]) -> Dict[str, Any]:
    """PR-T5 — `{"admin": x}` → kelima modul penggantinya bernilai x; id baru yang disebut langsung menang."""
    out: Dict[str, Any] = {}
    for k, v in (levels or {}).items():
        for nk in MODULE_ALIASES.get(k, []):
            out[nk] = v
    out.update({k: v for k, v in (levels or {}).items() if k not in MODULE_ALIASES})
    return out


def levels_available(module_id: str) -> List[str]:
    """PR-T5 — tingkat yang berlaku untuk modul ini. Tanpa aksi `view` di sumber daya mana pun = modul sakelar
    (`none`/`manage`, layar: Mati/Nyala); satu-satunya aksi semua sumber dayanya `view` = `none`/`view`."""
    acts = [full_actions(r) for r in MODULE_BY_ID[module_id]["resources"]]
    if not any("view" in a for a in acts):
        return ["none", "manage"]
    if all(set(a) <= {"view"} for a in acts):
        return ["none", "view"]
    return list(LEVELS)


def view_excludes(module_id: str) -> List[str]:
    """PR-T5 — label sumber daya yang DIBUANG pada "Lihat saja" karena tidak punya aksi lihat."""
    if "view" not in levels_available(module_id):
        return []
    return [RESOURCE_LABEL.get(r, r) for r in MODULE_BY_ID[module_id]["resources"] if "view" not in full_actions(r)]


def level_error(module_id: str, level: str) -> str:
    return (f"Tingkat “{LEVEL_LABEL.get(level, level)}” tidak berlaku untuk modul "
            f"“{MODULE_BY_ID[module_id]['label']}”.")


def check_levels(levels: Dict[str, Any]) -> None:
    """PR-T5 — `ValueError` bila ada tingkat di luar `levels_available` modulnya (alias diperluas dulu)."""
    for module_id, level in expand_aliases(levels).items():
        lvl = level.get("level") if isinstance(level, dict) else level
        if module_id in MODULE_BY_ID and lvl in LEVELS and lvl not in levels_available(module_id):
            raise ValueError(level_error(module_id, lvl))


def apply_levels(base: Dict[str, List[str]], levels: Dict[str, str]) -> Dict[str, List[str]]:
    """Terapkan tingkat per modul ke matriks aksi. Modul yang tidak disebut tetap utuh.
    PR-T5: id lama `admin` diperluas (`MODULE_ALIASES`); tingkat yang tidak berlaku → `ValueError` (`check_levels`)."""
    check_levels(levels)
    out = {k: list(v) for k, v in (base or {}).items()}
    for module_id, level in expand_aliases(levels).items():
        mod = MODULE_BY_ID.get(module_id)
        if not mod or level not in LEVELS:
            continue
        for r in mod["resources"]:
            if level == "none":
                out.pop(r, None)
            elif level == "view":
                if "view" in full_actions(r):
                    out[r] = ["view"]
                else:
                    out.pop(r, None)
            else:
                out[r] = full_actions(r)
    return out


def nav_for_levels(levels: Dict[str, str]) -> Dict[str, List[str]]:
    levels = expand_aliases(levels)   # PR-T5 — `custom_roles.levels` lama ber-id `admin`
    add, remove = set(ALWAYS_NAV), set()
    for m in MODULE_CATALOG:
        lvl = (levels.get(m["id"]) or {}) if isinstance(levels.get(m["id"]), dict) else levels.get(m["id"])
        lvl = lvl.get("level") if isinstance(lvl, dict) else lvl
        (remove if lvl in (None, "none") else add).update(m["nav"])
    # menu yang dibuka oleh modul lain yang aktif tidak boleh ikut dicabut
    remove -= add
    return {"add": sorted(add), "remove": sorted(remove)}


def public_catalog() -> List[Dict[str, Any]]:
    """PR-T5 — + `levels_available`, `view_excludes`, `sensitive_actions` per modul."""
    return [{**m, "actions": {r: full_actions(r) for r in m["resources"]},
             "levels_available": levels_available(m["id"]), "view_excludes": view_excludes(m["id"]),
             "sensitive_actions": sensitive_actions_of(m["id"])} for m in MODULE_CATALOG]


#: PR-T5 (PR-UX-30) — aksi berisiko PER AKSI; nilai = kalimat akibat ("Peran ini bisa …"). Hanya memunculkan
#: peringatan di editor peran (ikon di "Atur rinci", kalimat di dialog "Periksa sebelum menyimpan"); izin tidak berubah.
_SENSITIVE_GROUPS: List[Tuple[str, Tuple[Tuple[str, str], ...]]] = [
    ("membuka periode yang sudah ditutup dan mencatat bertanggal mundur",
     (("period", "unlock"), ("period", "backdate"), ("accounting", "reopen"))),
    ("membatalkan jurnal dan menutup buku", (("accounting", "void"), ("accounting", "manage"))),
    ("membayar pemasok dan mencairkan dana",
     (("vendor_bill", "pay"), ("contra_bon", "pay"), ("landed_cost", "pay"), ("cash_advance", "disburse"))),
    ("membebaskan atau mengubah denda", (("penalty", "waive"), ("penalty", "adjust"))),
    ("membatalkan kwitansi, faktur pajak, atau rencana bayar",
     (("ar_receipt", "void"), ("tax_invoice", "cancel"), ("payment_plan", "void"))),
    ("mengirim barang sebelum lunas dan mengubah pesanan terkunci",
     (("order", "release_unpaid"), ("order", "override"), ("order", "approve_price_edit"))),
    ("mengelola gaji dan melihat data pribadi karyawan", (("hr", "manage_payroll"), ("hr", "view_pii"))),
    ("menghapus data induk",
     (("product", "delete"), ("product", "retire"), ("customer", "delete"), ("supplier", "delete"),
      ("warehouse", "delete"), ("uom", "delete"), ("entity", "delete"))),
    ("mengelola akun dan hak akses orang lain",
     (("user", "create"), ("user", "update"), ("user", "delete"), ("permission", "update"))),
    ("mengubah pengaturan perusahaan", (("settings", "manage"),)),
    ("melihat HPP dan margin", (("costing", "view"), ("ai", "view_margin"), ("od_pricing", "view_cost"))),
    ("menyetujui nilai persediaan, melepas aset, dan mencatat akrual insentif",
     (("inventory", "approve_value"), ("fixed_asset", "dispose"), ("sales_force", "post"))),
    ("mengatur perangkat dan alat sistem", (("rfid_device", "configure"), ("system_tools", "configure"))),
]
SENSITIVE_ACTIONS: Dict[Tuple[str, str], str] = {pair: kalimat for kalimat, pairs in _SENSITIVE_GROUPS
                                                 for pair in pairs}


def sensitive_actions_of(module_id: str) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for r in MODULE_BY_ID[module_id]["resources"]:
        for a in full_actions(r):
            if (r, a) in SENSITIVE_ACTIONS:
                out.setdefault(r, {})[a] = SENSITIVE_ACTIONS[(r, a)]
    return out


#: Label manusia untuk sumber daya izin (dipakai "Konfigurasi lanjutan" di editor peran).
RESOURCE_LABEL = {
    "accounting": "Akuntansi & Buku Besar", "gl_mapping": "Pemetaan Akun", "approval": "Matriks Persetujuan", "ar_receipt": "Kwitansi / Uang Masuk (AR)",
    "audit": "Jejak Audit", "budget": "Anggaran", "cash": "Kas & Bank", "cash_advance": "Kasbon / Uang Muka",
    "cash_settlement": "Pertanggungjawaban Kas", "color": "Pustaka Warna", "contra_bon": "Kontrabon",
    "customer": "Pelanggan", "design_request": "Permintaan Desain", "design_ownership": "Kepemilikan Desain (white/customer label)", "document": "Dokumen & Cetak",
    "document_delivery": "Pengiriman Dokumen", "entity": "Badan Usaha", "esign": "Tanda Tangan Elektronik",
    "finance_amendment": "Amandemen Keuangan", "finance_case": "Kasus Keuangan", "fixed_asset": "Aset Tetap",
    "hr": "SDM / Karyawan", "input_tax": "Faktur Pajak Masukan", "inspection": "Inspeksi & QC",
    "interco": "Transaksi Antar PT (barang)", "interco_finance": "Keuangan Antar PT", "interco_price": "Harga Internal Antar PT", "internal_request": "Permintaan Internal (PIN)",
    "inventory": "Stok & Persediaan", "label": "Label & RFID", "landed_cost": "Landed Cost", "logistics": "Pengiriman & Logistik",
    "makloon": "Mitra Makloon", "makloon_order": "Order Makloon", "order": "Pesanan Penjualan (SO)",
    "payment_plan": "Rencana Pembayaran", "payment_variance": "Selisih Pembayaran", "pdf_template": "Template PDF",
    "penalty": "Denda", "period": "Periode & Tutup Buku", "permission": "Peran & Hak Akses", "price_approval": "Persetujuan Harga",
    "pricelist": "Daftar Harga", "process_recipe": "Resep Proses", "product": "Produk & Varian", "production": "Produksi",
    "purchase_order": "Pesanan Pembelian (PO)", "purchase_requisition": "Permintaan Pembelian (PR)", "purchase_return": "Retur Pembelian",
    "reports": "Laporan", "rfq": "RFQ / Penawaran", "rnd": "Riset & Sample", "sales_return": "Retur Penjualan",
    "sample_order": "Pesanan Sample (SOS)", "scheduler": "Penjadwal Otomatis", "settings": "Pengaturan Sistem", "supplier": "Pemasok",
    "supplier_contract": "Kontrak Pemasok", "supplier_item": "Barang Pemasok", "tax_invoice": "Faktur Pajak Keluaran",
    "template": "Template Dokumen", "transfer": "Transfer Antar Gudang", "uom": "Satuan", "user": "Akun Pengguna",
    "vehicle_log": "Log Kendaraan", "vendor_bill": "Tagihan Supplier", "warehouse": "Gudang", "wms": "Operasi Gudang (WMS)",
    "goods_receipt": "Kedatangan Barang (GRN)",
    "md_quality": "MD Quality (warna & handfeel)", "qc": "QC (4-point & random check)",
    "field_visibility": "Visibilitas Atribut Stok",
    "grade_master": "Master Grade Mutu",
    "od_fulfillment": "Pemenuhan Pesanan Khusus (supplier/makloon)",
    "od_pricing": "Harga Pesanan Khusus (kunci, harga PIC, biaya kontrak)",
    "repair_order": "Perbaikan / Celup Ulang Roll",
    "data_export": "Pusat Export Data",
    # PR-T2
    "sales_force": "Tim Sales: Target, Insentif & Penugasan", "credit_override": "Pengecualian Batas Kredit",
    "costing": "HPP & Margin Produk", "manager_home": "Beranda Manajer",
    "system_tools": "Kebersihan Data & Alat Sistem", "rfid_device": "Perangkat RFID & Handheld",
    "ai": "Asisten Tanya KN", "ai_template": "Templat Laporan Tanya KN",
    # PR-T5 — label yang belum ada di kamus server (teks dari kamus layar lama `auditLabels.js`).
    "marketing": "Pemasaran",
}

ACTION_LABEL = {
    "view": "Lihat", "create": "Buat", "update": "Ubah", "delete": "Hapus", "approve": "Setujui", "reject": "Tolak",
    "lock": "Kunci harga final", "set_price": "Isi harga (PIC Special Order)",
    "view_cost": "Lihat biaya kontrak, margin & supplier",
    "confirm": "Konfirmasi", "cancel": "Batalkan", "print": "Cetak", "export": "Ekspor", "import": "Impor",
    "adjust": "Penyesuaian", "admin": "Administrasi", "approve_count": "Setujui hitung", "approve_value": "Setujui nilai & jurnal pendaftaran awal", "approve_payment": "Setujui bayar", "cutting_config": "Atur kemampuan cutting lokasi", "cutting_receive": "Terima hasil potong (Admin Cutting)",
    "assess": "Nilai", "assign": "Tugaskan", "award": "Tetapkan pemenang", "backdate": "Tanggal mundur", "claim": "Klaim",
    "claim_approve": "Setujui klaim", "complete": "Selesaikan", "configure": "Konfigurasi", "convert": "Konversi",
    "cycle_count": "Stock opname", "decide": "Putuskan", "deliver": "Serahkan / kirim", "disburse": "Cairkan",
    "dispatch": "Dispatch", "dispose": "Lepas aset", "exact_cut": "Potong roll (pas)", "generate": "Generate", "hold": "Hold / tahan", "inspect": "Inspeksi", "invoice": "Buat faktur",
    "issue": "Terbitkan", "manage": "Kelola", "manage_attendance": "Kelola absensi", "manage_bom": "Kelola BOM",
    "manage_org": "Kelola struktur", "manage_payroll": "Kelola payroll", "manage_settings": "Kelola pengaturan", "pay": "Bayar",
    "pegging": "Pegging", "policy": "Atur kebijakan retur", "override": "Override / edit SO", "approve_price_edit": "Setujui ubah harga/diskon",
    "propose": "Usulkan", "random_check": "Random check", "receive": "Terima", "release": "Rilis", "reopen": "Buka kembali", "release_hold": "Lepas HOLD desain (PIC Designer)", "paper_check": "Centang print paper per ronde (Designer)", "choose_route": "Pilih jalur pemenuhan (supplier/makloon)", "override_default": "Menyimpang dari sumber default master", "realize": "Realisasi PR → PO/MKO", "pic_decide": "Keputusan PIC atas uji ulang gagal", "override_fail": "Override hasil uji gagal (tetap tercatat gagal)", "assess_labdip": "Catat hasil labdip", "assess_handfeel": "Catat hasil handfeel", "assess_proofing": "Catat hasil proofing", "decide_labdip": "Setujui hasil labdip", "decide_handfeel": "Setujui hasil handfeel", "decide_proofing": "Setujui hasil proofing",
    "replace": "Ganti", "report": "Laporan", "resolve": "Selesaikan kasus", "return": "Retur", "run": "Jalankan", "scan": "Scan",
    "send": "Kirim", "settle": "Lunasi", "ship": "Kirim barang", "sign": "Tandatangani", "submit": "Ajukan", "tax": "Pajak",
    "record_cutloss": "Catat qty cacat cutloss (QC)", "split_cutloss": "Proses pemecahan roll cutloss",
    "post_logistics": "Pilih akun & jurnal ongkir retur", "decide_compensation": "Putus nilai cutloss/diskon retur",
    "decide_rolls": "Terima / tolak per roll retur",
    "review_credit_note": "Tinjau nota kredit batal item (koreksi/terbitkan/batalkan)",
    "release_unpaid": "Kirim tanpa lunas (pengecualian termin CBD/DP)",
    "record_loss": "Catat susut/hilang di mitra", "approve_loss": "Setujui susut di atas toleransi",
    "activate": "Aktif / nonaktifkan", "grade": "Lihat grade", "lot": "Lihat LOT", "origin": "Lihat asal lokal/impor",
    "unlock": "Buka kunci", "untagged_override": "Pengecualian roll tanpa tag", "verify": "Verifikasi", "view_pii": "Lihat data pribadi", "void": "Void", "waive": "Bebaskan",
    # Label khusus satu pasangan `<sumber daya>.<aksi>` (didahulukan editor peran atas label aksi umum).
    "cash.configure": "Kelola rekening kas & bank",   # PK-17
    # PR-T2 — aksi baru pengganti gerbang nama peran
    "revoke": "Cabut akses perangkat", "view_margin": "Lihat margin & laba kotor",
    "view_stock_value": "Lihat nilai persediaan", "extend_rounds": "Buka ronde di atas batas",
    "retire": "Nonaktifkan / hapus permanen master",
    "treat_cutloss": "Pilih potongan cacat: masuk BS atau dibuang",
    "sales_force.post": "Catat akrual ke buku besar", "sales_force.assign": "Pindahkan pelanggan ke sales lain",
    "rnd.manage_org": "Kelola divisi R&D", "rnd.report": "Laporan penilaian desainer & papan SLA",
    "goods_receipt.configure": "Ganti mode penerimaan", "warehouse.configure": "Ubah struktur & profil gudang",
    "accounting.reopen": "Buka kembali periode & tembus blokir akun sementara",
    "inspection.release": "Lepas / tolak tahanan barang", "od_pricing.unlock": "Buka kunci harga final",
    "system_tools.configure": "Jalankan & kembalikan pembersihan, lepas kunci proses",
    "rfid_device.configure": "Daftarkan & atur perangkat", "ai.manage": "Lihat pemakaian & atur aturan asisten",
    "ai.configure": "Pengaturan teknis asisten & buka riwayat pengguna lain",
}
# PK-45 — izin kredit pelanggan (modul Pelanggan & CRM) dan pesanan tanpa PPN (modul Pesanan Penjualan).
ACTION_LABEL.update({"manage_credit": "Ubah plafon & blokir kredit", "tax_override": "Buat pesanan tanpa PPN"})
# PR-T4 — KPI & komisi sales lain (modul Pesanan Penjualan; dulu daftar nama peran di `_kpi_scope`).
ACTION_LABEL.update({"order.view_sales_kpi": "Lihat KPI & komisi sales lain"})
# PR-T5 — aksi yang belum berlabel (`set` dari kamus layar lama `auditLabels.js`).
ACTION_LABEL.update({"count": "Hitung", "review": "Tinjau", "close": "Tutup", "set": "Atur"})
#: PR-T2 — label aksi templat laporan Tanya KN = judul templat.
ACTION_LABEL.update({f"ai_template.{t['id']}": t["title"] for t in AI_TEMPLATES})


def clean_permissions(perms: Any) -> Dict[str, List[str]]:
    """Validasi matriks aksi rinci: sumber daya & aksi harus dikenal; aksi apa pun menyiratkan 'view'."""
    if not isinstance(perms, dict):
        raise ValueError("Format izin rinci tidak dikenal.")
    out: Dict[str, List[str]] = {}
    for res, acts in perms.items():
        full = full_actions(res)
        if not full:
            raise ValueError(f"Sumber daya izin “{res}” tidak dikenal.")
        chosen = [a for a in full if a in set(acts or [])]
        bad = [a for a in (acts or []) if a not in full]
        if bad:
            raise ValueError(f"Aksi {bad} tidak berlaku untuk “{RESOURCE_LABEL.get(res, res)}”.")
        if chosen and "view" in full and "view" not in chosen:
            chosen.insert(0, "view")
        if chosen:
            out[res] = chosen
    return out


# ─── RELEVANSI NOTIFIKASI ──────────────────────────────────────────────────────
# `link` notifikasi = layar tujuan. Nilai lama yang bukan id menu dipetakan di sini.
LINK_ALIASES = {
    "approvals": "approval-inbox", "finance": "finance-tower", "pending-so": "orders",
    "design-gallery": "cs-design-gallery", "so": "orders", "po": "purchasing",
}


#: Fase 4 · R5 (26 Okt) — id menu/tab yang SUMBER IZIN layarnya bukan sumber daya modul pembukanya. Tab "Lot &
#: Silsilah" ikut modul Stok & Persediaan (menu peran kustom tetap dari modul itu), tetapi seluruh `/api/lots*` dijaga
#: middleware `field_visibility` (izin `lot`): sales punya `inventory.view` namun tanpa visibilitas LOT, jadi tab
#: tampil lalu berbunyi "Registri LOT tidak tersedia untuk peran Anda". Dengan sumber `field_visibility`,
#: `roles.accessBlocks` menyembunyikannya otomatis bagi peran tanpa izin itu. Catatan: pemeriksa frontend hanya
#: menguji "ada aksi apa pun" pada sumber daya — peran kustom ber-`field_visibility` tanpa `lot` (mis. hanya `grade`)
#: masih melihat tab (lalu 403 jujur dari server); presisi per-aksi butuh perubahan `config/roles.js` (berkas bersama).
VIEW_RESOURCE_OVERRIDES: Dict[str, List[str]] = {
    "inventory-lots": ["field_visibility"],
    # FIX-1 (audit B1b UI-47) — layar Pengiriman (`/api/logistics/*`) dijaga izin `logistics` SAJA; modulnya juga memuat
    # `vehicle_log`, sehingga manajer berizin log kendaraan tanpa `logistics` melihat menunya lalu "Permission ditolak:
    # logistics.view" mentah. Kini menu disembunyikan bila izin `logistics` tidak ada (Log Kendaraan tetap ikut modul).
    "logistics": ["logistics"],
    # KF-T1 — tab Pusat Pengaturan hanya tampil bagi yang bisa MEMBACA isinya: pemegang `settings.view`, atau
    # pemegang izin pengubah kunci di kelompok tab itu (`permission[0]` kunci registry; dijaga tes
    # `tests_mem/test_KFT1_izin_pengaturan.py::U14` terhadap `configGroupViews.js`).
    "settings-config": ["settings"],
    "settings-cfg-finance": ["settings"],
    "settings-cfg-documents": ["settings"],
    "settings-cfg-notify": ["settings"],
    "settings-cfg-system": ["settings"],
    "settings-cfg-approval": ["settings", "rnd"],
    "settings-cfg-rnd": ["settings", "rnd"],
    "settings-cfg-sales": ["settings", "sales_return"],
    "settings-cfg-hr": ["settings", "hr"],
    "settings-cfg-purchasing": ["settings", "makloon"],
    "settings-cfg-warehouse": ["settings", "uom", "inventory", "goods_receipt"],
    # PR-T2 — menu hanya untuk pemegang izinnya (bukan semua pemegang modul Laporan / Penjualan).
    "costing": ["costing"],
    "incentive-rates": ["sales_force"],
}
# KF-T6 — tab Kontrol dua orang dibuka izin `settings` (GET /api/kontrol/aturan = `settings.view`).
VIEW_RESOURCE_OVERRIDES["settings-dual-control"] = ["settings"]
# KF-T2 — kunci `interco_payment.*` (kelompok "antar-entitas") diubah pemegang `entity.update`; aturan KF-T1 (U14): tab
# kelompok itu juga terbuka bagi pemegang izin pengubah kuncinya.
VIEW_RESOURCE_OVERRIDES["settings-cfg-finance"] = ["settings", "entity"]
# KP-T7 — kunci pengingat/penjadwal (izin `scheduler.configure`) masuk kelompok "notifikasi", "keuangan-dasar",
# "persetujuan", dan "rnd"; aturan KF-T1 (U14): tab kelompok itu juga terbuka bagi pemegang izin pengubah kuncinya.
for _v in ("settings-cfg-notify", "settings-cfg-finance", "settings-cfg-approval", "settings-cfg-rnd"):
    VIEW_RESOURCE_OVERRIDES[_v] = [*VIEW_RESOURCE_OVERRIDES[_v], "scheduler"]
del _v


#: PR-T5 — menu yang butuh AKSI tertentu (bukan sekadar "ada aksi apa pun pada sumber daya modulnya"). Dikirim
#: bersama `view_resources` di `GET /api/auth/me` sebagai `view_actions`; `roles.accessBlocks` menyembunyikan menu bila
#: tidak satu pun pasangan dipegang. Syaratnya sama dengan halaman awal meja itu (`role_registry.HOME_CHOICES`).
VIEW_ACTION_REQUIREMENTS: Dict[str, List[Tuple[str, str]]] = {
    "sales-admin-desk": [("order", "confirm")],
    "finance-desk": [("payment_variance", "decide")],
    "md-desk": [("design_request", "view")],
    "warehouse-admin-desk": [("wms", "view")],
    "sample-admin-desk": [("sample_order", "view")],
}


def view_actions_index() -> Dict[str, List[List[str]]]:
    return {k: [list(p) for p in v] for k, v in VIEW_ACTION_REQUIREMENTS.items()}


def _holds_any(perms: Dict[str, List[str]], pairs: List[Tuple[str, str]]) -> bool:
    return any(a in (perms.get(r) or []) or "*" in (perms.get(r) or []) for r, a in pairs)


def view_resources_index() -> Dict[str, List[str]]:
    """L01 LN-015 — id menu/tab → sumber daya izin modul yang membukanya (untuk menyaring navigasi
    dari izin EFEKTIF, bukan nama peran)."""
    idx: Dict[str, set] = {}
    for m in MODULE_CATALOG:
        for v in m["nav"]:
            idx.setdefault(v, set()).update(m["resources"])
    for v, res in VIEW_RESOURCE_OVERRIDES.items():   # R5 — sumber izin layar yang sebenarnya menggantikan modul
        idx[v] = set(res)
    return {k: sorted(v) for k, v in idx.items()}


def all_nav_ids() -> set:
    return {v for m in MODULE_CATALOG for v in m["nav"]}


def nav_allowed_for_perms(perms: Dict[str, List[str]]) -> List[str]:
    """Semua id menu/tab yang boleh dibuka pemegang izin `perms` (tingkat ≥ Lihat)."""
    allowed = set(ALWAYS_NAV)
    for m in MODULE_CATALOG:
        if level_of(perms, m["id"])["level"] != "none":
            allowed.update(m["nav"])
    allowed -= {v for v, need in VIEW_ACTION_REQUIREMENTS.items() if not _holds_any(perms, need)}   # PR-T5
    return sorted(allowed)


def labels_dictionary() -> Dict[str, Dict[str, str]]:
    """PR-T5 — SATU kamus label (`GET /api/access/labels`): sumber daya, aksi (termasuk label khusus `<sumber daya>.<aksi>`),
    dan label modul pemilik tiap sumber daya. Dipakai editor peran, penerjemah pesan penolakan, dan jejak audit."""
    return {"resources": dict(RESOURCE_LABEL), "actions": dict(ACTION_LABEL),
            "modules": {r: m["label"] for m in MODULE_CATALOG for r in m["resources"]}}


def module_label_of(resource: str) -> str:
    """Label modul pemilik sebuah sumber daya izin (untuk pesan Z6 "Minta Admin menambahkan akses '…'")."""
    for m in MODULE_CATALOG:
        if resource in m["resources"]:
            return m["label"]
    return resource


def module_of_link(link: str) -> str:
    target = LINK_ALIASES.get(link or "", link or "")
    for m in MODULE_CATALOG:
        if target in m["nav"]:
            return m["id"]
    return ""
