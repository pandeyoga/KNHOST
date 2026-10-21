"""KATALOG MODUL HAK AKSES — bahasa manusia di atas matriks izin teknis.

Satu "modul" = kelompok sumber daya izin (`permissions_config`) + menu/tab yang
membukanya. Admin mengatur per modul dengan 3 tingkat: none · view · manage.
"""
from typing import Any, Dict, List

from permissions_config import DEFAULT_PERMISSIONS, EXTRA_ACTIONS

LEVELS = ("none", "view", "manage")
LEVEL_LABEL = {"none": "Tidak ada", "view": "Lihat saja", "manage": "Kelola penuh"}

#: Menu yang selalu terlihat oleh peran kustom apa pun.
ALWAYS_NAV = ["hr-my-profile"]

MODULE_CATALOG: List[Dict[str, Any]] = [
    {"id": "penjualan", "group": "Penjualan", "label": "Pesanan Penjualan",
     "description": "Pesanan (SO), koreksi, retur, pesanan khusus, dan permintaan internal antar badan usaha.",
     "resources": ["order", "sales_return", "internal_request", "od_fulfillment"],
     "nav": ["penjualan", "sales", "sales-orders", "orders", "amendments", "returns", "returns-hub",
             "return-policies", "special-orders", "internal-requests"]},
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
             "md-categories", "color-library", "md-uoms"]},
    {"id": "pricing", "group": "Penjualan", "label": "Harga & Persetujuan Harga",
     "description": "Daftar harga per badan usaha, harga per pelanggan, dan persetujuan harga khusus.",
     "resources": ["pricelist", "price_approval"],
     "nav": ["penjualan", "products-pricing", "pricelist", "cs-price-list",
             "approval-inbox", "price-approvals"]},
    {"id": "purchasing", "group": "Pembelian", "label": "Pembelian & Pengadaan",
     "description": "Permintaan pembelian (PR), RFQ, pesanan pembelian (PO), dan retur pembelian.",
     "resources": ["purchase_order", "purchase_requisition", "rfq", "purchase_return"],
     "nav": ["pembelian", "sourcing", "reorder", "purchase-requisitions", "rfq",
             "purchase-orders", "purchasing", "po-board", "blanket-po",
             "approval-inbox", "purchase-approval", "purchase-returns", "returns-hub"]},   # FE-03: tab Hutang milik modul payable
    {"id": "supplier", "group": "Pembelian", "label": "Pemasok & Makloon",
     "description": "Master pemasok, mitra makloon, kontrak, barang supplier, resep proses & order makloon.",
     "resources": ["supplier", "supplier_contract", "supplier_item", "makloon",
                   "makloon_order", "process_recipe"],
     "nav": ["pembelian", "master-pembelian", "suppliers", "makloons", "supplier-contracts",
             "supplier-items", "process-recipes", "purchase-orders", "makloon-orders", "makloon-claim-recap",
             "makloon-claims"]},
    {"id": "payable", "group": "Pembelian", "label": "Hutang Supplier & Kontrabon",
     "description": "Tagihan supplier, kontrabon (tukar faktur), landed cost, dan faktur pajak masukan.",
     "resources": ["vendor_bill", "contra_bon", "landed_cost", "input_tax"],
     "nav": ["pembelian", "accounts-payable", "vendor-bills", "contra-bons", "landed-cost",
             "keuangan", "tax-hub", "input-tax"]},
    {"id": "interco", "group": "Pembelian", "label": "Transaksi Antar Badan Usaha",
     "description": "Jual-beli antar PT dalam grup, settlement, dan saldo pasangan PT.",
     "resources": ["interco", "interco_finance", "interco_price"],
     "nav": ["pembelian", "interco-transactions", "interco-returns", "returns-hub"]},   # FE-03: tab Hutang milik modul payable
    {"id": "rnd", "group": "Produk & Desain", "label": "Riset & Sample (R&D)",
     "description": "Spesifikasi produk, permintaan sample, labdip, handfeel, proofing, dan laporan R&D.",
     "resources": ["rnd"],
     "nav": ["rnd-hub", "rnd-specs", "rnd-samples", "rnd-labdip", "rnd-handfeel",
             "rnd-proofing", "rnd-reports"]},
    {"id": "design", "group": "Produk & Desain", "label": "Desain & Desainer",
     "description": "Permintaan desain, galeri desain & pattern, KPI desainer.",
     "resources": ["design_request"],
     "nav": ["designer-hub", "design-requests", "designer-kpi", "rnd-designs",
             "cs-design-gallery", "rnd-divisions"]},
    {"id": "marketing", "group": "Penjualan", "label": "Marketing & Sosial Media",
     "description": "Kalender konten, kampanye, persetujuan konten, performa post.",
     "resources": ["marketing"],
     "nav": ["marketing-hub", "mkt-calendar", "mkt-campaigns", "mkt-analytics", "mkt-accounts"]},
    {"id": "warehouse_ops", "group": "Gudang", "label": "Operasi Gudang (WMS)",
     "description": "Barang masuk/keluar, lokasi rak, data gudang, label, produksi in-house, RFID.",
     "resources": ["wms", "goods_receipt", "warehouse", "label", "production"],
     # FE-03 — tab Barang Masuk/Keluar & hub RFID ikut modul ini (dulu `rfid` = ID tak dikenal menu).
     "nav": ["gudang", "wms-operations", "operations", "goods-receipts", "wms-outbound", "qc-inspection",
             "wms-locations", "md-warehouses", "production", "escalations", "rfid-hub", "cs-rfid-lokasi",
             "cs-rfid-tags", "cs-rfid-devices", "cs-rfid-gate",
             # F-11-layar — retur pelanggan yang menunggu scan terima/kirim/tiba (tampilan tanpa uang)
             "returns-hub", "returns"]},
    {"id": "inventory", "group": "Gudang", "label": "Stok & Persediaan",
     "description": "Status stok & ATP, lot & silsilah, stock opname, transfer antar gudang/entitas.",
     "resources": ["inventory", "transfer"],
     "nav": ["gudang", "stock-atp", "inventory-board", "stock-buckets", "inventory-lots",
             "wms-operations", "operations", "interco-transfers", "cs-stock-analytics"]},   # FE-03: tab tampak dari alias interco-transfers
    {"id": "inspection", "group": "Gudang", "label": "Inspeksi & QC",
     "description": "SPK inspeksi, hasil pemeriksaan warna/handfeel, keputusan terima/tolak.",
     "resources": ["inspection"],
     "nav": ["gudang", "wms-operations", "inspections", "qc-inspection"]},
    {"id": "md_quality", "group": "Gudang", "label": "MD Quality",
     "description": "Warna & handfeel vs sample ACC (penerimaan PO & hasil makloon), lepas/tolak tahanan.",
     "resources": ["md_quality"],
     "nav": ["gudang", "wms-operations", "qc-inspection", "inspections"]},   # FE-03: tab tampak dari alias inspections
    {"id": "qc", "group": "Gudang", "label": "QC (4-point & random check)",
     "description": "Cacat 4-point & grade per roll, random check roll di stok.",
     "resources": ["qc"],
     # F-11-layar — retur pelanggan yang menunggu/menjalani QC (tampilan tanpa uang)
     "nav": ["gudang", "wms-operations", "qc-inspection", "inspections", "returns-hub", "returns"]},   # FE-03: tab tampak dari alias inspections
    {"id": "logistics", "group": "Gudang", "label": "Pengiriman & Kendaraan",
     "description": "Pengiriman (ekspedisi/armada), foto muat & POD, log kendaraan.",
     "resources": ["logistics", "vehicle_log"],
     "nav": ["gudang", "logistics", "kas-aset", "vehicle-logs"]},
    {"id": "ar", "group": "Keuangan", "label": "Uang Masuk, Piutang & Faktur Pajak",
     "description": "Kwitansi AR, piutang, rencana bayar, denda, selisih bayar, faktur pajak keluaran.",
     "resources": ["ar_receipt", "tax_invoice", "payment_plan", "penalty", "payment_variance"],
     "nav": ["keuangan", "ar-aging", "advance-report", "payment-plans", "store-credit",
             "tax-hub", "tax-invoices", "cs-pajak"]},
    {"id": "finance_ops", "group": "Keuangan", "label": "Kas, Bank & Kasus Keuangan",
     "description": "Dasbor keuangan, rekening & saldo, transaksi kas, rekonsiliasi bank, kasus uang nyangkut, amandemen.",
     "resources": ["cash", "finance_case", "finance_amendment"],
     "nav": ["keuangan", "finance-tower", "cash-bank", "bank-accounts", "cash-management",
             "bank-reconciliation", "finance-cases"]},
    {"id": "accounting", "group": "Keuangan", "label": "Akuntansi & Tutup Buku",
     "description": "Buku besar, laporan keuangan, anggaran, aset tetap, tutup buku & buka periode.",
     "resources": ["accounting", "period", "budget", "fixed_asset", "gl_mapping"],
     "nav": ["keuangan", "ledger", "general-ledger", "chart-of-accounts", "gl-account-mappings", "fin-reports",
             "financial-statements", "profitability", "cashflow-forecast", "budget",
             "consolidation", "closing", "period-unlock", "posting-failures", "kas-aset", "fixed-assets"]},
    {"id": "petty_cash", "group": "Keuangan", "label": "Kas Kecil (PD / LPJ)",
     "description": "Pengajuan dana, pertanggungjawaban, kategori beban.",
     "resources": ["cash_advance", "cash_settlement"],
     "nav": ["kas-aset", "petty-cash", "cash-advances", "settlements", "expense-categories"]},
    {"id": "hr", "group": "Organisasi", "label": "SDM & Penggajian",
     "description": "Karyawan, struktur organisasi, presensi, cuti, lembur, payroll, KPI.",
     "resources": ["hr"],
     "nav": ["hrd", "hr-people", "hr-employees", "hr-org-units", "hr-attendance-hub",
             "hr-attendance", "hr-leave", "hr-overtime", "hr-live-tracking",
             "hr-attendance-setup", "hr-payroll-hub", "hr-payroll-runs", "hr-payslips",
             "hr-kpi-hub", "cs-kpi"]},
    {"id": "documents", "group": "Alat", "label": "Dokumen, Cetak & Tanda Tangan",
     "description": "Pusat dokumen, jejak dokumen, pusat cetak, e-sign, pengiriman dokumen.",
     "resources": ["document", "esign", "document_delivery", "pdf_template"],
     "nav": ["document-center", "doc-trace", "documents"]},
    {"id": "reports", "group": "Alat", "label": "Laporan & Analitik",
     "description": "Dasbor analitik, margin & HPP, BI keuangan/SDM, jejak audit.",
     "resources": ["reports", "audit"],
     "nav": ["analytics", "reports", "costing", "bi-finance", "cs-bi-hrd"]},   # FE-03: cs-bi-sales/stock tidak ada lagi di menu
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
     "resources": ["grade_master"], "nav": ["grade-master"]},
    {"id": "field_visibility", "group": "Penjualan", "label": "Visibilitas Atribut Stok (grade · LOT · asal)",
     "description": "Boleh melihat grade, LOT (internal/supplier/dye lot) dan asal lokal/impor di layar, API, detail, "
                    "ekspor dan dokumen cetak. Tanpa izin ini atribut disembunyikan server.",
     "resources": ["field_visibility"], "nav": []},
    {"id": "sales_profile", "group": "Penjualan", "label": "Profil POV Sales Komersial",
     "description": "Menandai peran sebagai POV komersial Sales: hanya varian warna; GRADE SELALU disembunyikan "
                    "walau izin visibilitas grade dicentang (berlaku juga saat trial).",
     "resources": ["sales_pov"], "nav": []},
    {"id": "admin", "group": "Organisasi", "label": "Pengaturan, Pengguna & Hak Akses",
     "description": "Pengaturan sistem, badan usaha, akun pengguna, peran & hak akses, penjadwal. Hati-hati: 'Kelola penuh' berarti bisa mengubah hak akses orang lain.",
     "resources": ["user", "permission", "settings", "entity", "scheduler"],
     "nav": ["settings-hub", "settings-config", "entities-access", "admin", "entity-masters",
             "scheduler", "pdf-templates", "domain-registry", "approval-rules"],
     "sensitive": True},
]

MODULE_BY_ID = {m["id"]: m for m in MODULE_CATALOG}
_ADMIN = DEFAULT_PERMISSIONS["admin"]


def full_actions(resource: str) -> List[str]:
    return list(_ADMIN.get(resource, [])) or list(EXTRA_ACTIONS.get(resource, []))


def level_of(perms: Dict[str, List[str]], module_id: str) -> Dict[str, Any]:
    """Tingkat efektif sebuah modul dari daftar aksi mentah."""
    mod = MODULE_BY_ID[module_id]
    acts = set()
    for r in mod["resources"]:
        acts.update(perms.get(r, []) or [])
    if not acts:
        return {"level": "none", "partial": False}
    if acts <= {"view"}:
        return {"level": "view", "partial": False}
    full = all(set(perms.get(r, []) or []) >= set(full_actions(r)) for r in mod["resources"])
    return {"level": "manage", "partial": not full}


def levels_of(perms: Dict[str, List[str]]) -> Dict[str, Dict[str, Any]]:
    return {m["id"]: level_of(perms, m["id"]) for m in MODULE_CATALOG}


def apply_levels(base: Dict[str, List[str]], levels: Dict[str, str]) -> Dict[str, List[str]]:
    """Terapkan tingkat per modul ke matriks aksi. Modul yang tidak disebut tetap utuh."""
    out = {k: list(v) for k, v in (base or {}).items()}
    for module_id, level in (levels or {}).items():
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
    add, remove = set(ALWAYS_NAV), set()
    for m in MODULE_CATALOG:
        lvl = (levels.get(m["id"]) or {}) if isinstance(levels.get(m["id"]), dict) else levels.get(m["id"])
        lvl = lvl.get("level") if isinstance(lvl, dict) else lvl
        (remove if lvl in (None, "none") else add).update(m["nav"])
    # menu yang dibuka oleh modul lain yang aktif tidak boleh ikut dicabut
    remove -= add
    return {"add": sorted(add), "remove": sorted(remove)}


def public_catalog() -> List[Dict[str, Any]]:
    return [{**m, "actions": {r: full_actions(r) for r in m["resources"]}} for m in MODULE_CATALOG]


#: Label manusia untuk sumber daya izin (dipakai "Konfigurasi lanjutan" di editor peran).
RESOURCE_LABEL = {
    "accounting": "Akuntansi & Buku Besar", "gl_mapping": "Pemetaan Akun", "approval": "Matriks Persetujuan", "ar_receipt": "Kwitansi / Uang Masuk (AR)",
    "audit": "Jejak Audit", "budget": "Anggaran", "cash": "Kas & Bank", "cash_advance": "Kasbon / Uang Muka",
    "cash_settlement": "Pertanggungjawaban Kas", "color": "Pustaka Warna", "contra_bon": "Kontrabon",
    "customer": "Pelanggan", "design_request": "Permintaan Desain", "document": "Dokumen & Cetak",
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
    "field_visibility": "Visibilitas Atribut Stok", "sales_pov": "Profil POV Sales",
    "grade_master": "Master Grade Mutu",
    "od_fulfillment": "Pemenuhan Pesanan Khusus (supplier/makloon)",
    "data_export": "Pusat Export Data",
}

ACTION_LABEL = {
    "view": "Lihat", "create": "Buat", "update": "Ubah", "delete": "Hapus", "approve": "Setujui", "reject": "Tolak",
    "confirm": "Konfirmasi", "cancel": "Batalkan", "print": "Cetak", "export": "Ekspor", "import": "Impor",
    "adjust": "Penyesuaian", "admin": "Administrasi", "approve_count": "Setujui hitung", "approve_payment": "Setujui bayar", "cutting_config": "Atur kemampuan cutting lokasi", "cutting_receive": "Terima hasil potong (Admin Cutting)",
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
    "record_loss": "Catat susut/hilang di mitra", "approve_loss": "Setujui susut di atas toleransi",
    "activate": "Aktif / nonaktifkan", "grade": "Lihat grade", "lot": "Lihat LOT", "origin": "Lihat asal lokal/impor",
    "commercial": "POV komersial (grade selalu tersembunyi)",
    "unlock": "Buka kunci", "untagged_override": "Pengecualian roll tanpa tag", "verify": "Verifikasi", "view_pii": "Lihat data pribadi", "void": "Void", "waive": "Bebaskan",
}


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


def view_resources_index() -> Dict[str, List[str]]:
    """L01 LN-015 — id menu/tab → sumber daya izin modul yang membukanya (untuk menyaring navigasi
    dari izin EFEKTIF, bukan nama peran)."""
    idx: Dict[str, set] = {}
    for m in MODULE_CATALOG:
        for v in m["nav"]:
            idx.setdefault(v, set()).update(m["resources"])
    return {k: sorted(v) for k, v in idx.items()}


def all_nav_ids() -> set:
    return {v for m in MODULE_CATALOG for v in m["nav"]}


def nav_allowed_for_perms(perms: Dict[str, List[str]]) -> List[str]:
    """Semua id menu/tab yang boleh dibuka pemegang izin `perms` (tingkat ≥ Lihat)."""
    allowed = set(ALWAYS_NAV)
    for m in MODULE_CATALOG:
        if level_of(perms, m["id"])["level"] != "none":
            allowed.update(m["nav"])
    return sorted(allowed)


def module_of_link(link: str) -> str:
    target = LINK_ALIASES.get(link or "", link or "")
    for m in MODULE_CATALOG:
        if target in m["nav"]:
            return m["id"]
    return ""
