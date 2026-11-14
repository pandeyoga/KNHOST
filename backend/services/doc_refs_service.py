"""FASE G-4 — **RELASI DOKUMEN TERSIMPAN** (`refs[]` dua arah) + Jejak Dokumen.

MASALAH NYATA PEMILIK
---------------------
*"SO customer pending → KN harus PO ke supplier → banyak surat lahir tapi saling
tidak mereferensikan → tracking & penelusuran retur susah."*

Sebelum fase ini relasi antar dokumen hanya **diturunkan saat dibaca**
(`document_relations_service`) dan hanya untuk 2 jangkar (SO & PO). Akibatnya:

* dokumen di tengah rantai (Faktur, Kwitansi, Nota Retur, Vendor Bill) **buntu** —
  tidak bisa dipakai sebagai titik masuk penelusuran;
* dokumen cetak tidak pernah menyebut nomor referensinya, sehingga penerima kertas
  tidak bisa menghubungkan surat satu dengan lainnya;
* tidak ada satu pun invarian yang bisa berkata "dokumen turunan ini yatim".

Fase ini menyimpan relasi sebagai **data** di setiap dokumen:

    refs: [{rel, doc_type, doc_id, doc_number, note, at}]

`rel` memakai kosakata tetap (lihat `REL_INVERSE`) dan **selalu ditulis dua arah**,
sehingga penelusuran bisa dimulai dari dokumen mana pun. Penulisan terjadi di titik
LAHIR dokumen (bukan batch semalam), plus `backfill()` idempotent untuk data lama.

Kenapa tidak menghapus `document_relations_service`? Karena layar lama (timeline SO/PO)
memakainya dan bentuk "stage" itu masih berguna. G-4 menambah lapisan **fakta tersimpan**
di bawahnya; keduanya tidak saling meniadakan dan invarian INV-REF menjaga agar fakta
tersimpan tidak tertinggal dari kenyataan.
"""
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core_utils import now_iso, safe_doc
from db import db
from services.config_resolver import resolve

# ── Kosakata relasi ─────────────────────────────────────────────────────────
# `rel` dibaca dari sudut pandang PEMILIK dokumen terhadap TARGET-nya.
REL_INVERSE: Dict[str, str] = {
    "parent": "child",
    "child": "parent",
    "amends": "amended_by",
    "amended_by": "amends",
    "corrects": "corrected_by",
    "corrected_by": "corrects",
    "reverses": "reversed_by",
    "reversed_by": "reverses",
    "settles": "settled_by",
    "settled_by": "settles",
    "fulfills": "fulfilled_by",
    "fulfilled_by": "fulfills",
    "issued": "issued_by",
    "issued_by": "issued",
    "replaces": "replaced_by",
    "replaced_by": "replaces",
    # FASE I — dokumen inspeksi MENGACU ke sample yang di-ACC (labdip/handfeel) sebagai
    # dasar penilaian "warna sesuai?". Ini bukan hubungan induk-anak: inspeksi tidak
    # LAHIR dari sample, ia hanya membandingkan diri dengannya. Karena itu pasangannya
    # dibuat sendiri, dan `references` DILUAR `PARENT_RELS` supaya INV-REF-01 tidak
    # menganggap sample sebagai induk yang mengesahkan dokumen inspeksi.
    "references": "referenced_by",
    "referenced_by": "references",
    # Jurnal & kas DITURUNKAN saat dibaca (source_id / ref_id) — bukan refs[] tersimpan.
    "journal_of": "journaled_by",
    "journaled_by": "journal_of",
}

REL_LABEL: Dict[str, str] = {
    "parent": "Berasal dari",
    "child": "Menurunkan",
    "amends": "Mengamandemen",
    "amended_by": "Diamandemen oleh",
    "corrects": "Mengoreksi",
    "corrected_by": "Dikoreksi oleh",
    "reverses": "Membalik",
    "reversed_by": "Dibalik oleh",
    "settles": "Melunasi",
    "settled_by": "Dilunasi oleh",
    "fulfills": "Memenuhi",
    "fulfilled_by": "Dipenuhi oleh",
    "issued": "Menerbitkan",
    "issued_by": "Diterbitkan oleh",
    "replaces": "Mengganti",
    "replaced_by": "Diganti oleh",
    "references": "Mengacu ke",
    "referenced_by": "Diacu oleh",
    "journal_of": "Jurnal atas",
    "journaled_by": "Dijurnal di",
    # DRIFT D6 DITUTUP (FASE I, 2026-08-23): label `applied_to` DICABUT. Ia berdiri di
    # sini tanpa pasangan di `REL_INVERSE`, jadi `link(..., rel="applied_to")` SELALU
    # melempar `RefsError` — cacat yang tertidur karena tak seorang pun memakainya
    # (grep: 0 pemakaian sebagai relasi). Yang berbahaya bukan kegagalannya, melainkan
    # bahwa agen/pengembang berikutnya membaca REL_LABEL sebagai DAFTAR PILIHAN lalu
    # memilih nilai yang mustahil. Kosakata mati lebih baik dihapus daripada dijaga.
    # Kebutuhan nyata "dokumen ini mengacu ke dokumen itu" kini dilayani pasangan
    # `references`/`referenced_by` di atas.
}

# Relasi yang menandakan "saya lahir dari dokumen lain" → dipakai INV-REF-01.
PARENT_RELS = {"parent", "amends", "corrects", "reverses", "settles", "fulfills", "issued_by"}


# ── Peta jenis dokumen (SATU tempat; jangan disalin ke skrip lain) ──────────
def _T(doc_type: str, collection: str, number: str, label: str,
       view: str = "", focus_type: str = "", order: int = 50,
       needs_parent: bool = False, filter_: Optional[Dict[str, Any]] = None,
       source_fk: Optional[Sequence[str]] = None, tab: str = "", focus_from: str = "",
       perm: Optional[Tuple[str, str]] = None) -> Dict[str, Any]:
    """Satu baris peta dokumen.

    `source_fk` = kolom penghubung NYATA yang menandakan dokumen ini memang LAHIR
    dari dokumen lain (mis. `wms_tasks.po_id`). Dipakai INV-REF-01 supaya invarian
    JUJUR: surat yang punya sumber wajib menaut sumbernya, sedangkan dokumen yang
    sah berdiri sendiri (penerimaan tanpa PO, kwitansi uang muka tanpa alokasi,
    tagihan biaya langsung tanpa PO) tidak dituduh yatim. Tanpa pembedaan ini gate
    akan memerah karena transaksi yang benar — dan gate yang "memerah palsu" cepat
    diabaikan orang.

    PK-44 (IA-04, K-18) — tujuan tautan: `view` (layar yang DIRENDER perute; diuji statik terhadap
    `AppViewRouter.jsx`), `tab` (tab di layar itu), `focus_type` (jenis yang dibaca pembaca fokus layar),
    `focus_from` (field dokumen yang menjadi `focus_id` — kosong = id dokumen itu sendiri; mis. surat jalan dibuka
    lewat pesanan induknya `order_id`). `perm` = izin LIHAT modul sumber (sumber_daya, aksi): nominal & tombol buka
    simpul hanya untuk pemegangnya (penyaring PK-17, `SOURCE_PERMISSION` diturunkan dari sini). `None` = tidak
    disaring (dokumen tanpa nilai uang).
    """
    return {"doc_type": doc_type, "collection": collection, "number": number,
            "label": label, "view": view, "focus_type": focus_type or doc_type,
            "order": order, "needs_parent": needs_parent, "filter": filter_ or {},
            "source_fk": list(source_fk or []), "tab": tab, "focus_from": focus_from,
            "perm": tuple(perm) if perm else None}


DOC_TYPES: Dict[str, Dict[str, Any]] = {d["doc_type"]: d for d in [
    _T("special_order", "special_orders", "number", "Pesanan Khusus", "special-orders", order=5),
    _T("purchase_requisition", "purchase_requisitions", "number", "Permintaan Pembelian (PR)",
       "purchase-requisitions", order=10),
    _T("rfq", "rfqs", "number", "Permintaan Penawaran (RFQ)", "rfq", order=12,
       # P-0 — RFQ yang lahir dari PR menaut PR-nya (rantai PO → RFQ → PR → SO).
       source_fk=["pr_id"]),
    _T("supplier_contract", "supplier_contracts", "contract_number", "Kontrak Pemasok",
       "supplier-contracts", order=14),
    _T("purchase_order", "purchase_orders", "po_number", "Pesanan Pembelian (PO)", "purchasing", order=20,
       # P-0 (prasyarat FASE P) — PO yang LAHIR dari PR wajib menaut PR-nya. `pr_id`
       # hanya terisi pada PO hasil realisasi PR/award RFQ, jadi PO pembelian rutin
       # yang sah berdiri sendiri TIDAK dituduh yatim (aturan `source_fk`).
       source_fk=["pr_id"], perm=("purchase_order", "view")),
    # PK-44 — tugas terima tidak punya layar rincian sendiri: dibuka lewat PO induknya di Kedatangan Barang (tab
    # penerimaan per PO). Tanpa PO (`po_id` kosong) → layar dibuka tanpa fokus.
    _T("grn", "wms_tasks", "id", "Penerimaan Barang (GRN)", "goods-receipts", order=25,
       needs_parent=True, filter_={"flow_type": "inbound"}, source_fk=["po_id"],
       tab="inbound", focus_type="purchase_order", focus_from="po_id"),
    _T("goods_receipt", "goods_receipts", "number", "Kedatangan Barang (Surat Jalan)", "goods-receipts",
       order=24),
    _T("landed_cost", "landed_cost_vouchers", "number", "Biaya Masuk (Landed Cost)", "landed-cost",
       order=27, needs_parent=True, source_fk=["po_ids"], perm=("landed_cost", "view")),
    _T("vendor_bill", "vendor_bills", "bill_number", "Tagihan Pemasok",
       "vendor-bills", order=30, needs_parent=True, source_fk=["po_id", "makloon_order_id"],
       perm=("vendor_bill", "view")),
    # FASE G-7 — kontrabon: satu dokumen menggabungkan banyak faktur supplier satu siklus.
    _T("contra_bon", "contra_bons", "number", "Kontrabon (Tukar Faktur)", "contra-bons",
       order=31, perm=("vendor_bill", "view")),
    _T("purchase_return", "purchase_returns", "number", "Retur Beli", "purchase-returns",
       order=32, needs_parent=True, source_fk=["po_id"], perm=("purchase_return", "view")),
    _T("makloon_order", "makloon_orders", "mko_number", "Order Makloon", "makloon-orders", order=35),
    _T("sales_order", "sales_orders", "number", "Pesanan Penjualan (SO)", "orders", order=40,
       perm=("order", "view")),
    # PK-44 — tugas ambil dibuka di Barang Keluar (pembaca `wms_task` sudah ada).
    _T("picking_task", "wms_tasks", "id", "Tugas Pengambilan", "wms-outbound", order=42,
       needs_parent=True, filter_={"flow_type": "outbound"}, source_fk=["order_id"], focus_type="wms_task"),
    # PK-44 — surat jalan tidak punya layar rincian sendiri: dibuka lewat pesanan induknya.
    _T("shipment", "shipments", "shipment_no", "Surat Jalan / Pengiriman", "orders",
       order=44, needs_parent=True, source_fk=["order_id"], focus_type="sales_order", focus_from="order_id"),
    _T("tax_invoice", "tax_invoices", "number", "Faktur Pajak", "tax-invoices",
       order=46, needs_parent=True, source_fk=["order_id", "replaces_id"], perm=("tax_invoice", "view")),
    # PK-44 — kwitansi dibuka di Keuangan › Piutang › Penagihan & Penerimaan (MN-T1 memindahkan tab Penagihan dari
    # CRM ke layar `collection-worklist`); riwayat kwitansi mencari nomor dan menyorot barisnya.
    _T("ar_receipt", "ar_receipts", "number", "Kwitansi Pelanggan", "collection-worklist",
       order=48, needs_parent=True, source_fk=["allocations"], perm=("ar_receipt", "view")),
    _T("sales_return", "sales_returns", "number", "Retur Jual", "returns",
       order=50, needs_parent=True, source_fk=["order_id"], perm=("sales_return", "view")),
    _T("doc_amendment", "doc_amendments", "number", "Amandemen Dokumen", "amendments",
       order=52, needs_parent=True, source_fk=["doc_id"]),
    _T("credit_note", "credit_notes", "number", "Nota Kredit / Debit", "amendments",
       order=54, needs_parent=True, source_fk=["order_id", "amendment_id"]),
    # FASE G-2 — jadwal bayar & nota denda adalah DOKUMEN (bisa ditelusuri & dicetak).
    # PK-44 — `tab` = kunci tab `PaymentPlansView` (jadwal · denda · selisih).
    _T("payment_plan", "payment_plans", "number", "Rencana Pembayaran", "payment-plans",
       order=56, needs_parent=True, source_fk=["doc_id"], tab="jadwal", perm=("payment_plan", "view")),
    _T("penalty", "penalties", "number", "Nota Denda Keterlambatan", "payment-plans",
       order=58, needs_parent=True, source_fk=["doc_id"], tab="denda", perm=("penalty", "view")),
    # FASE G-3 — keputusan selisih pembayaran (lebih/kurang bayar) juga DOKUMEN bernomor.
    _T("payment_variance", "payment_variance_decisions", "number",
       "Keputusan Selisih Pembayaran", "payment-plans", order=59, needs_parent=True,
       source_fk=["receipt_id", "bill_id"], tab="selisih", perm=("payment_variance", "view")),
    # PK-44 — transfer & stock opname dibuka di Operasi Gudang pada tabnya (pembaca fokus sudah ada).
    _T("warehouse_transfer", "warehouse_transfers", "code", "Surat Jalan Transfer",
       "operations", order=60, tab="transfer"),
    # FASE G-6 — antar-PT adalah JUAL-BELI: dokumen kembar (SO/SJ/Invoice internal di
    # penjual, PO internal/Vendor Bill di pembeli) + settlement/netting. Tanpa
    # terdaftar di sini, dokumen antar-PT tidak bisa ditelusuri/dicetak dari Pusat
    # Dokumen dan jejak "barangnya pindah lewat tugas gudang mana" berhenti.
    # PK-44 — `tab` = kunci tab `IntercoView`.
    _T("interco_transaction", "interco_transactions", "number",
       "Transaksi Antar-PT (Jual-Beli Internal)", "interco-transactions", order=64, tab="transactions",
       perm=("interco", "view")),
    _T("interco_settlement", "interco_settlements", "number",
       "Pelunasan Antar-PT", "interco-transactions", order=65, tab="settlements",
       perm=("interco_finance", "view")),
    # FASE G-6b — retur antar-PT (dokumen kembar nota retur ↔ nota kredit internal)
    # & faktur pajak MASUKAN internal (pasangan faktur keluaran di PT penjual).
    # PK-44 — retur antar-PT tinggal di layar Retur Antar-PT (`interco-returns`, L08), bukan di tab Antar-PT.
    _T("interco_return", "interco_returns", "number",
       "Retur Antar-PT", "interco-returns", order=66, tab="returns", perm=("interco", "view")),
    _T("input_tax_invoice", "tax_invoices_in", "number",
       "Faktur Pajak Masukan", "input-tax", order=67, perm=("input_tax", "view")),
    _T("cycle_count", "cycle_count_sessions", "number", "Stock Opname", "operations", order=62, tab="cycle"),
    # FASE F — R&D: spesifikasi & permintaan sample adalah DOKUMEN bernomor yang
    # menjadi HULU rantai (spec → sample → kontrak → PO). Tanpa ini kontrak harga
    # tidak bisa menjawab "harga ini dari mana".
    _T("md_spec", "md_specs", "number", "Spesifikasi Produk (R&D)", "rnd-specs", order=2),
    _T("md_sample", "md_samples", "number", "Permintaan Sample (Labdip/Proofing)",
       "rnd-samples", order=3, needs_parent=False, source_fk=["spec_id"]),
    # FASE G-9 — kasus keuangan adalah DOKUMEN bernomor: sumbernya (kwitansi/mutasi/tagihan)
    # dan dokumen turunannya (jurnal/kas/nota denda) harus bisa ditelusuri dua arah.
    _T("finance_case", "finance_cases", "number", "Kasus Keuangan", "finance-cases",
       order=61, needs_parent=False, perm=("finance_case", "view")),
    # FASE G-7 — pembayaran kontrabon adalah SATU transaksi kas untuk banyak faktur.
    # Tanpa jenis dokumen ini, jejak "uang keluarnya lewat mana" berhenti di kontrabon
    # dan petugas harus mencari sendiri di layar Kas & Bank.
    # PK-44 — `cash-bank` adalah id hub, bukan layar: transaksi kas dibuka di Pengelolaan Kas (cari nomor, sorot).
    _T("cash_transaction", "cash_transactions", "number", "Transaksi Kas / Bank",
       "cash-management", order=63, needs_parent=False, perm=("cash", "view")),
    # FASE E-7 (E7d) — permintaan internal adalah HULU transaksi antar-PT: tanpa
    # terdaftar di sini, pertanyaan "transaksi antar-PT ini untuk siapa/kenapa"
    # berhenti di catatan bebas.
    _T("internal_request", "internal_requests", "number",
       "Permintaan Internal (Antar-PT)", "internal-requests", order=6),
    # FASE E-7 (E7f) — pinjaman uang antar-PT (dokumen kembar piutang ↔ utang).
    _T("interco_loan", "interco_loans", "number",
       "Pinjaman Antar-PT", "interco-transactions", order=68, tab="loans", perm=("interco_finance", "view")),
    # FASE D — permintaan desain: HULU rantai desain (permintaan → artwork galeri →
    # spesifikasi → produk). Tanpa terdaftar di sini, pertanyaan "artwork ini diminta
    # untuk pesanan siapa" berhenti di catatan bebas.
    _T("design_request", "design_requests", "number", "Permintaan Desain",
       "design-requests", order=1, source_fk=["so_id"]),
    # FASE I — dokumen inspeksi: SPK QC yang LAHIR dari dokumen lain (PO / order
    # makloon / retur). `needs_parent=True` + `source_fk=["ref_doc_id"]` supaya
    # INV-REF-01 menuntut tautannya, tetapi hanya untuk dokumen yang memang punya
    # sumber (inspeksi berdiri sendiri tidak dituduh yatim).
    _T("repair_order", "repair_orders", "number", "Perbaikan / Celup Ulang", "repair-orders", order=27),   # UAT 24 Okt (P7)
    _T("inspection", "inspections", "number", "Inspeksi & QC", "inspections",
       order=26, needs_parent=True, source_fk=["ref_doc_id"]),
    # PK-44 (IA-10) — gaji, kas kecil, dan aset tetap ikut bisa ditelusuri ke jurnalnya. Tidak ada koleksi/field
    # baru: koleksi & nomor yang sudah ada. LPJ wajib berinduk PD (`cash_advance_id`, ditaut saat lahir +
    # `backfill`). Jurnal gaji ber-`source_id` "{entity_id}:{period}" → kasus khusus di `derived_refs`.
    _T("payroll_run", "hr_payroll_runs", "number", "Penggajian", "hr-payroll-runs", order=70,
       perm=("hr", "view")),
    _T("cash_advance", "cash_advances", "number", "Pengajuan Dana (PD)", "cash-advances", order=71,
       perm=("cash_advance", "view")),
    _T("cash_settlement", "cash_advance_settlements", "number", "Pertanggungjawaban Dana (LPJ)", "settlements",
       order=72, needs_parent=True, source_fk=["cash_advance_id"], perm=("cash_settlement", "view")),
    _T("fixed_asset", "fin_fixed_assets", "number", "Aset Tetap", "fixed-assets", order=73,
       perm=("fixed_asset", "view")),
    # Ujung rantai akuntansi — jurnal otomatis tiap dokumen (tautan diturunkan dari source_id).
    _T("journal_entry", "journal_entries", "number", "Jurnal", "general-ledger", order=90,
       perm=("accounting", "view")),
]}

# source_type jurnal → doc_type sumbernya (selain yang namanya sudah sama dengan doc_type). Semua `source_id` di
# bawah berawalan id dokumennya (diperiksa PK-44 di `gl_service`); gaji = kasus khusus `PAYROLL_SOURCE_TYPES`.
JOURNAL_SOURCE_TYPE: Dict[str, str] = {
    "shipment_revenue": "shipment", "shipment_cogs": "shipment",
    "subcon_issue": "makloon_order", "subcon_receipt": "makloon_order",
    "subcon_service": "vendor_bill", "goods_receipt": "grn",
    "advance_reclass": "sales_order", "contra_bon_deduction": "contra_bon",
    # PK-44 (IA-10)
    "petty_cash_settlement": "cash_settlement",
    "fixed_asset_acquisition": "fixed_asset", "fixed_asset_depreciation": "fixed_asset",
    "fixed_asset_disposal": "fixed_asset",
    "makloon_claim": "makloon_order", "makloon_material_loss": "makloon_order",
    "subcon_service_unabsorbed": "makloon_order", "subcon_issue_reversal": "makloon_order",
    "penalty_reversal": "penalty", "penalty_payment": "penalty",
    "payment_variance_writeoff": "payment_variance", "payment_variance_alloc": "payment_variance",
    "payment_variance_reversal": "payment_variance", "ap_variance_writeoff": "payment_variance",
    "cash_transaction_void": "cash_transaction", "vendor_bill_reversal": "vendor_bill",
}
# PK-44 — jurnal gaji: `source_id` = "{entity_id}:{period}" (satu penggajian aktif per PT per bulan), bukan id run.
PAYROLL_SOURCE_TYPES = ("payroll_run", "payroll_pay")
#: Catatan relasi LPJ → PD (saat lahir dan `backfill`; satu teks supaya tidak bercabang).
LPJ_NOTE = "pertanggungjawaban PD"
DERIVED_RELS = {"journal_of", "journaled_by"}

# Koleksi → doc_type kanonik (untuk PDF doc_type yang berbagi koleksi, mis. `invoice`
# & `delivery_note` sama-sama berasal dari `sales_orders`).
COLLECTION_TO_TYPE: Dict[str, str] = {}
for _d in DOC_TYPES.values():
    if not _d["filter"]:
        COLLECTION_TO_TYPE.setdefault(_d["collection"], _d["doc_type"])


class RefsError(ValueError):
    """Kesalahan relasi dokumen dengan pesan siap tampil (Bahasa Indonesia)."""


# ── Konfigurasi (registry FASE G-0 — tidak ada angka hardcode) ──────────────
async def _cfg(key: str, entity_id: str = "") -> Any:
    res = await resolve(key, {"entity_id": entity_id or ""})
    return res["value"]


async def autolink_enabled(entity_id: str = "") -> bool:
    return bool(await _cfg("docref.autolink_enabled", entity_id))


async def trace_max_depth(entity_id: str = "") -> int:
    return int(await _cfg("docref.trace_max_depth", entity_id))


async def parent_required(entity_id: str = "") -> bool:
    """Dipakai INV-REF-01: apakah dokumen turunan WAJIB punya induk hidup."""
    return bool(await _cfg("docref.require_parent", entity_id))


async def pdf_options(entity_id: str = "") -> Dict[str, Any]:
    """Opsi blok referensi pada dokumen cetak (dibaca `services/pdf_service.py`)."""
    return {
        "show": bool(await _cfg("docref.show_in_pdf", entity_id)),
        "qr": bool(await _cfg("docref.qr_in_pdf", entity_id)),
        "max": int(await _cfg("docref.pdf_max_refs", entity_id)),
    }


# ── Util dokumen ────────────────────────────────────────────────────────────
def type_of_collection(collection: str) -> str:
    return COLLECTION_TO_TYPE.get(collection, "")


def _meta(doc_type: str) -> Dict[str, Any]:
    meta = DOC_TYPES.get(doc_type)
    if not meta:
        raise RefsError(f"Jenis dokumen '{doc_type}' belum terdaftar di peta relasi.")
    return meta


async def load_doc(doc_type: str, doc_id: str) -> Optional[Dict[str, Any]]:
    meta = _meta(doc_type)
    row = await db[meta["collection"]].find_one({"id": doc_id}, {"_id": 0})
    return safe_doc(row) if row else None


def number_of(doc_type: str, doc: Dict[str, Any]) -> str:
    """Nomor dokumen yang LAYAK DICETAK.

    `wms_tasks` tidak punya nomor manusiawi (hanya id teknis `wms_xxx`) — kalau id itu
    ikut tercetak di kop dokumen, pembaca kertas melihat sampah. Karena itu tugas
    gudang diberi nomor turunan yang bisa dibaca (`GRN-XXXXXX` / `PICK-XXXXXX`) sambil
    tetap merujuk id aslinya di data.
    """
    meta = DOC_TYPES.get(doc_type) or {}
    field = meta.get("number") or "number"
    if doc_type in ("grn", "picking_task"):
        prefix = "GRN" if doc_type == "grn" else "PICK"
        tail = str(doc.get("id") or "")[-6:].upper()
        return f"{prefix}-{tail}" if tail else prefix
    return str(doc.get(field) or doc.get("number") or doc.get("id") or "")


def _title_of(doc_type: str, doc: Dict[str, Any]) -> str:
    for k in ("customer_name", "supplier_name", "makloon_name", "product_name",
              "partner_name", "warehouse_name", "reason_label", "description"):
        if doc.get(k):
            return str(doc[k])
    return DOC_TYPES.get(doc_type, {}).get("label", doc_type)


def _amount_of(doc: Dict[str, Any]) -> float:
    for k in ("grand_total", "total_amount", "amount", "gross_amount", "net_amount",
              "total_est_amount", "acquisition_cost", "total_pengeluaran"):   # PK-44 — aset tetap, LPJ
        if doc.get(k) not in (None, ""):
            try:
                return float(doc[k])
            except (TypeError, ValueError):
                continue
    return 0.0


def _date_of(doc: Dict[str, Any]) -> str:
    for k in ("created_at", "receipt_date", "faktur_date", "order_date", "bill_date", "date"):
        if doc.get(k):
            return str(doc[k])
    return ""


# UAT 24 Okt (P16.2) — jenis jejak → jenis PDF di `pdf_resolvers.DOC_REGISTRY` (nama sama kecuali di sini).
# Kosong = jenis ini belum bisa dicetak; kartu jejak menulis "belum bisa dicetak".
_PDF_OF = {"makloon_order": "makloon_spk", "warehouse_transfer": "transfer", "inspection": "inspection_spk"}


def pdf_type_of(doc_type: str) -> str:
    from services.pdf_resolvers import DOC_REGISTRY
    t = _PDF_OF.get(doc_type, doc_type)
    return t if t in DOC_REGISTRY else ""


# ── PK-17 (K-18, IA-01) — nominal dokumen hanya untuk pemegang izin lihat modul sumbernya ─────────────
#: Jenis dokumen bernilai uang → izin LIHAT modul sumbernya. Jenis yang tidak terdaftar tidak disaring.
#: PK-44 — diturunkan dari `perm` di peta jenis dokumen (satu sumber; dulu daftar kedua yang ditulis tangan).
SOURCE_PERMISSION: Dict[str, Tuple[str, str]] = {t: m["perm"] for t, m in DOC_TYPES.items() if m.get("perm")}


def may_see_amount(doc_type: str, viewer_perms: Optional[Dict[str, List[str]]]) -> bool:
    """`viewer_perms=None` = pemanggil sistem (tanpa penyaringan)."""
    need = SOURCE_PERMISSION.get(doc_type)
    if viewer_perms is None or not need:
        return True
    acts = viewer_perms.get(need[0]) or []
    return need[1] in acts or "*" in acts


def redact_node(node: Dict[str, Any], viewer_perms: Optional[Dict[str, List[str]]]) -> Dict[str, Any]:
    """Simpul/butir rujukan tanpa nominal bila izin modul sumbernya tidak dipegang. Nomor, jenis, status, tanggal,
    dan judul tetap; tombol buka & cetak dimatikan (`can_open`, `pdf_doc_type`)."""
    if not node or may_see_amount(node.get("doc_type") or "", viewer_perms):
        return node
    node.update({"amount": None, "amount_hidden": True, "can_open": False, "pdf_doc_type": ""})
    return node


def link_of(doc_type: str, doc: Dict[str, Any]) -> Dict[str, Any]:
    """PK-44 (IA-04) — SATU-SATUNYA pembentuk tautan dokumen → layar: `{view, tab, focus_type, focus_id, number}`.

    Dipakai simpul Jejak Dokumen (`node_of`), panel referensi, dan linimasa proses
    (`document_relations_service._link`). `view` selalu layar yang dirender perute; `focus_id` diambil dari field
    `focus_from` bila ada (surat jalan → pesanan induk, tugas terima → PO induk), kosong bila field itu kosong
    (layar dibuka tanpa fokus). Menu yang disorot TIDAK dikirim (`nav_id`): layar menurunkannya dari menu peran
    (`resolveDeepLinkTarget`), karena id menu/tab berubah (MN-T1) sedangkan peta ini tidak boleh ikut basi.
    """
    meta = DOC_TYPES.get(doc_type) or {}
    src = meta.get("focus_from") or ""
    fid = (doc.get(src) if src else doc.get("id")) or ""
    return {"view": meta.get("view", ""), "tab": meta.get("tab", ""),
            "focus_type": meta.get("focus_type", doc_type), "focus_id": str(fid) if fid else "",
            "number": number_of(doc_type, doc)}


def node_of(doc_type: str, doc: Dict[str, Any]) -> Dict[str, Any]:
    meta = DOC_TYPES.get(doc_type, {})
    return {
        "key": f"{doc_type}:{doc.get('id')}",
        "doc_type": doc_type, "doc_id": doc.get("id"),
        "label": meta.get("label", doc_type),
        "number": number_of(doc_type, doc),
        "title": _title_of(doc_type, doc),
        "status": doc.get("status") or doc.get("payment_status") or "",
        "date": _date_of(doc),
        "amount": _amount_of(doc),
        "entity_id": doc.get("entity_id") or "",
        "link": link_of(doc_type, doc),
        "order": meta.get("order", 50),
        "pdf_doc_type": pdf_type_of(doc_type),
    }


# ── Penulisan relasi (dua arah, idempotent) ────────────────────────────────
def _same(a: Dict[str, Any], rel: str, doc_type: str, doc_id: str) -> bool:
    return (a.get("rel") == rel and a.get("doc_type") == doc_type
            and a.get("doc_id") == doc_id)


async def _push_ref(holder_type: str, holder_id: str, ref: Dict[str, Any]) -> bool:
    """Tulis 1 ref ke dokumen pemilik bila belum ada. Return True bila menambah."""
    meta = _meta(holder_type)
    coll = db[meta["collection"]]
    holder = await coll.find_one({"id": holder_id}, {"_id": 0, "refs": 1})
    # CATATAN: proyeksi `{_id:0, refs:1}` mengembalikan **dict kosong** untuk dokumen
    # yang belum punya `refs` — dan dict kosong itu falsy. Karena itu perbandingannya
    # WAJIB `is None`, bukan `not holder` (bug ini membuat backfill "berhasil" 0 tautan).
    if holder is None:
        return False
    for existing in holder.get("refs") or []:
        if _same(existing, ref["rel"], ref["doc_type"], ref["doc_id"]):
            return False
    await coll.update_one({"id": holder_id},
                          {"$push": {"refs": ref}, "$set": {"updated_at": now_iso()}})
    return True


async def link(src: Tuple[str, str], dst: Tuple[str, str], rel: str,
               note: str = "", force: bool = False) -> Dict[str, Any]:
    """Tautkan dua dokumen **dua arah**.

    `src` melihat `dst` sebagai `rel`; `dst` otomatis melihat `src` sebagai
    `REL_INVERSE[rel]`. Aman dipanggil berulang (dedupe by rel+target).

    Dipakai di titik LAHIR dokumen turunan; kegagalan tidak boleh menggagalkan
    transaksi bisnis (pemanggil membungkus dengan try/except).
    """
    if rel not in REL_INVERSE:
        raise RefsError(f"Relasi '{rel}' tidak dikenal. Pilihan: {', '.join(sorted(REL_INVERSE))}.")
    src_type, src_id = src
    dst_type, dst_id = dst
    if not (src_id and dst_id):
        return {"linked": 0, "reason": "id kosong"}
    src_doc = await load_doc(src_type, src_id)
    dst_doc = await load_doc(dst_type, dst_id)
    if not src_doc or not dst_doc:
        return {"linked": 0, "reason": "dokumen tidak ditemukan"}
    if not force and not await autolink_enabled(src_doc.get("entity_id") or ""):
        return {"linked": 0, "reason": "autolink dimatikan admin"}

    at = now_iso()
    a = await _push_ref(src_type, src_id, {
        "rel": rel, "doc_type": dst_type, "doc_id": dst_id,
        "doc_number": number_of(dst_type, dst_doc), "note": note, "at": at})
    b = await _push_ref(dst_type, dst_id, {
        "rel": REL_INVERSE[rel], "doc_type": src_type, "doc_id": src_id,
        "doc_number": number_of(src_type, src_doc), "note": note, "at": at})
    return {"linked": int(a) + int(b), "src": f"{src_type}:{src_id}", "dst": f"{dst_type}:{dst_id}",
            "rel": rel}


async def link_child(parent: Tuple[str, str], child: Tuple[str, str],
                     note: str = "", force: bool = False) -> Dict[str, Any]:
    """Gula sintaksis: dokumen turunan menunjuk induknya (`parent`) dan sebaliknya."""
    return await link(child, parent, "parent", note=note, force=force)


async def safe_link(src: Tuple[str, str], dst: Tuple[str, str], rel: str,
                    note: str = "") -> None:
    """Versi `link()` untuk dipasang di jalur transaksi bisnis.

    Penautan referensi adalah pelengkap jejak, BUKAN syarat sahnya transaksi:
    kegagalan (dokumen belum tersimpan, koleksi baru, dsb.) tidak boleh membatalkan
    pembuatan surat jalan/faktur/kwitansi. Karena itu semua galat ditelan di sini —
    dan `INV-REF-01/02` yang akan berteriak bila ada relasi yang tertinggal.
    """
    try:
        await link(src, dst, rel, note=note)
    except Exception:  # noqa: BLE001
        return


async def _payroll_run_of_journal(je: Dict[str, Any]) -> str:
    """PK-44 (IA-10) — penggajian pemilik jurnal gaji. Jurnal ber-`source_id` "{entity_id}:{period}" (memotong pada
    ":" dulu menghasilkan id PT). Utamakan run yang mencatat id jurnal ini; selain itu run (PT, periode) yang tidak
    dibatalkan (`existing_run` memakai kunci yang sama)."""
    jid = je.get("id") or ""
    if jid:
        run = await db.hr_payroll_runs.find_one(
            {"$or": [{"journal_id": jid}, {"paid_journal_id": jid}]}, {"_id": 0, "id": 1})
        if run:
            return run["id"]
    sid = str(je.get("source_id") or "")
    if sid.startswith("prun"):   # PK-22 — jurnal gaji berkunci id proses
        run = await db.hr_payroll_runs.find_one({"id": sid}, {"_id": 0, "id": 1})
        return (run or {}).get("id", "")
    ent, _, period = sid.partition(":")
    if not (ent and period):
        return ""
    run = await db.hr_payroll_runs.find_one(
        {"entity_id": ent, "period": period, "status": {"$ne": "void"}}, {"_id": 0, "id": 1})
    return (run or {}).get("id", "")


async def derived_refs(doc_type: str, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Tautan yang DITURUNKAN dari kolom sumber (jurnal & transaksi kas) — tidak disimpan."""
    import re as _re
    out: List[Dict[str, Any]] = []
    if doc_type == "journal_entry":
        st = doc.get("source_type") or doc.get("source") or ""
        if st in PAYROLL_SOURCE_TYPES:
            run_id = await _payroll_run_of_journal(doc)
            if run_id:
                out.append({"rel": "journal_of", "doc_type": "payroll_run", "doc_id": run_id, "note": st})
            return out
        tgt = JOURNAL_SOURCE_TYPE.get(st) or (st if st in DOC_TYPES else "")
        sid = str(doc.get("source_id") or "").split(":")[0]
        if tgt and sid:
            out.append({"rel": "journal_of", "doc_type": tgt, "doc_id": sid, "note": st})
        return out
    if doc_type == "payroll_run" and doc.get("id"):
        # PK-44 — jurnal gaji LAMA tidak berawalan id run: dicari dengan kunci "{entity_id}:{period}". PK-22 — jurnal
        # baru berkunci id proses (tertangkap pencarian `source_id` di bawah); kunci lama hanya untuk proses yang jurnalnya
        # memang terbit dengan kunci lama (`gl_service.payroll_source_id`), supaya proses kedua periode yang sama tidak
        # ikut menautkan jurnal proses yang di-void.
        from services import gl_service as _gl
        src = await _gl.payroll_source_id(doc)
        if src != doc["id"]:
            async for j in db.journal_entries.find(
                    {"source_type": {"$in": list(PAYROLL_SOURCE_TYPES)}, "source_id": src},
                    {"_id": 0, "id": 1, "number": 1, "source_type": 1}).limit(30):
                out.append({"rel": "journaled_by", "doc_type": "journal_entry", "doc_id": j["id"],
                            "doc_number": j.get("number", ""), "note": j.get("source_type", "")})
    if doc_type == "cash_transaction":
        if doc.get("ref_type") in DOC_TYPES and doc.get("ref_id"):
            out.append({"rel": "parent", "doc_type": doc["ref_type"], "doc_id": doc["ref_id"],
                        "note": "kas atas dokumen ini"})
    did = doc.get("id") or ""
    if not did:
        return out
    async for j in db.journal_entries.find(
            {"$or": [{"source_id": did}, {"source_id": {"$regex": f"^{_re.escape(did)}:"}}]},
            {"_id": 0, "id": 1, "number": 1, "source_type": 1}).limit(30):
        out.append({"rel": "journaled_by", "doc_type": "journal_entry", "doc_id": j["id"],
                    "doc_number": j.get("number", ""), "note": j.get("source_type", "")})
    if doc_type != "cash_transaction":
        async for c in db.cash_transactions.find({"ref_id": did}, {"_id": 0, "id": 1, "number": 1}).limit(30):
            out.append({"rel": "child", "doc_type": "cash_transaction", "doc_id": c["id"],
                        "doc_number": c.get("number", ""), "note": "transaksi kas"})
    return out


#: PK-43 (UX-13) — jurnal yang dibuat langsung di buku besar: tidak punya dokumen sumber.
JOURNAL_NO_SOURCE = ("manual", "closing", "reversal", "suspense_reclass")
#: PK-43 — jurnal kembar antar-PT berkunci `{pair_id}:{sisi}` (bukan id dokumen): dokumen sumbernya = dokumen pasangan
#: itu di buku PT jurnal (`pair_id` + `entity_id`).
JOURNAL_PAIR_TYPES = ("interco_transaction", "interco_return")


async def journal_source_doc(je: Dict[str, Any], allowed_entity_ids: Optional[Sequence[str]] = None,
                             viewer_perms: Optional[Dict[str, List[str]]] = None) -> Optional[Dict[str, Any]]:
    """PK-43 (UX-13, `02` L8) — dokumen sumber satu jurnal: `derived_refs` → `load_doc` → `node_of`.

    `None` untuk jurnal tanpa sumber (`JOURNAL_NO_SOURCE`) atau bila dokumennya tidak ditemukan. Selain itu
    `{doc_type, doc_id, number, label, link, link_hidden}`; `link` = `{view, focus_type, focus_id, tab}` (peta tujuan
    PK-44) atau `None` bila PT dokumen di luar `allowed_entity_ids` (`link_hidden="pt"`), izin lihat modul sumbernya
    tidak dipegang (`"izin"`, penyaring PK-17), atau jenisnya belum punya layar."""
    st = je.get("source_type") or je.get("source") or ""
    if not st or st in JOURNAL_NO_SOURCE:
        return None
    for ref in await derived_refs("journal_entry", je):
        if ref.get("rel") != "journal_of" or ref.get("doc_type") not in DOC_TYPES:
            continue
        doc = await load_doc(ref["doc_type"], ref["doc_id"])
        if not doc and ref["doc_type"] in JOURNAL_PAIR_TYPES:
            row = await db[DOC_TYPES[ref["doc_type"]]["collection"]].find_one(
                {"pair_id": ref["doc_id"], "entity_id": je.get("entity_id") or ""}, {"_id": 0})
            doc = safe_doc(row) if row else None
        if not doc:
            return None
        node = node_of(ref["doc_type"], doc)
        lk = node.get("link") or {}
        hidden = ""
        if node.get("entity_id") and allowed_entity_ids is not None and node["entity_id"] not in allowed_entity_ids:
            hidden = "pt"
        elif not may_see_amount(ref["doc_type"], viewer_perms):
            hidden = "izin"
        link = None if hidden or not lk.get("view") else {
            "view": lk["view"], "focus_type": lk.get("focus_type", ""), "focus_id": lk.get("focus_id", ""),
            "tab": lk.get("tab", "")}
        return {"doc_type": ref["doc_type"], "doc_id": doc.get("id") or ref["doc_id"], "number": node.get("number", ""),
                "label": node.get("label", ""), "link": link, "link_hidden": hidden}
    return None


async def all_refs(doc_type: str, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """refs[] tersimpan + tautan turunan (tanpa duplikat target)."""
    stored = list(doc.get("refs") or [])
    have = {(r.get("doc_type"), r.get("doc_id")) for r in stored}
    return stored + [{**r, "derived": True} for r in await derived_refs(doc_type, doc)
                     if (r["doc_type"], r["doc_id"]) not in have]


async def refs_of(doc_type: str, doc_id: str, resolve_targets: bool = True,
                  viewer_perms: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
    """Daftar referensi sebuah dokumen + status hidup/mati targetnya. PK-17: `viewer_perms` (izin peran pembaca;
    `None` = sistem) → butir & jangkar yang modul sumbernya tidak boleh dilihat tanpa nominal (`redact_node`)."""
    doc = await load_doc(doc_type, doc_id)
    if not doc:
        raise RefsError("Dokumen tidak ditemukan.")
    out: List[Dict[str, Any]] = []
    for r in await all_refs(doc_type, doc):
        row = dict(r)
        row["rel_label"] = REL_LABEL.get(r.get("rel", ""), r.get("rel", ""))
        row["label"] = DOC_TYPES.get(r.get("doc_type", ""), {}).get("label", r.get("doc_type", ""))
        row["known_type"] = r.get("doc_type") in DOC_TYPES
        if resolve_targets and row["known_type"]:
            tgt = await load_doc(r["doc_type"], r["doc_id"])
            row["alive"] = bool(tgt)
            if tgt:
                row["doc_number"] = number_of(r["doc_type"], tgt)
                row["status"] = tgt.get("status") or ""
                row["link"] = node_of(r["doc_type"], tgt)["link"]
        out.append(redact_node(row, viewer_perms))
    return {"doc_type": doc_type, "doc_id": doc_id,
            "number": number_of(doc_type, doc), "refs": out,
            "anchor": redact_node(node_of(doc_type, doc), viewer_perms)}


# ── Penelusuran (graf dari jangkar mana pun) ───────────────────────────────
async def trace(doc_type: str, doc_id: str, depth: Optional[int] = None,
                viewer_perms: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
    """Telusuri seluruh rantai dokumen dari jangkar mana pun (BFS atas `refs[]`).

    Kedalaman dibatasi `docref.trace_max_depth` (configurable) supaya graf besar
    tidak membekukan UI; sisa simpul dilaporkan lewat `truncated`.

    PK-17 (K-18) — `viewer_perms` = izin peran pembaca (`None` = pemanggil sistem): simpul yang modul sumbernya
    tidak boleh dilihat tetap tampil (nomor/jenis/status) tetapi tanpa nominal (`redact_node`).
    """
    anchor_doc = await load_doc(doc_type, doc_id)
    if not anchor_doc:
        raise RefsError("Dokumen tidak ditemukan.")
    max_depth = int(depth or await trace_max_depth(anchor_doc.get("entity_id") or ""))
    max_depth = max(1, min(max_depth, 8))

    seen: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    edge_seen = set()
    queue: List[Tuple[str, str, int]] = [(doc_type, doc_id, 0)]
    anchor_key = f"{doc_type}:{doc_id}"
    truncated = 0

    while queue:
        cur_type, cur_id, level = queue.pop(0)
        key = f"{cur_type}:{cur_id}"
        if key in seen:
            continue
        cur_doc = await load_doc(cur_type, cur_id)
        if not cur_doc:
            continue
        node = redact_node(node_of(cur_type, cur_doc), viewer_perms)
        node["level"] = level
        node["is_anchor"] = key == anchor_key
        seen[key] = node
        cur_refs = await all_refs(cur_type, cur_doc)
        if level >= max_depth:
            truncated += len(cur_refs)
            continue
        for r in cur_refs:
            t, i = r.get("doc_type"), r.get("doc_id")
            if not t or not i or t not in DOC_TYPES:
                continue
            ekey = "|".join(sorted([key, f"{t}:{i}"]))
            if ekey not in edge_seen:
                edge_seen.add(ekey)
                edges.append({"from": key, "to": f"{t}:{i}", "rel": r.get("rel", ""),
                              "rel_label": REL_LABEL.get(r.get("rel", ""), r.get("rel", "")),
                              "note": r.get("note", ""), "derived": bool(r.get("derived"))})
            if f"{t}:{i}" not in seen:
                queue.append((t, i, level + 1))

    nodes = sorted(seen.values(), key=lambda n: (n["order"], n.get("date") or ""))
    groups: List[Dict[str, Any]] = []
    for n in nodes:
        g = next((x for x in groups if x["doc_type"] == n["doc_type"]), None)
        if not g:
            g = {"doc_type": n["doc_type"], "label": n["label"],
                 "order": n["order"], "docs": []}
            groups.append(g)
        g["docs"].append(n)
    groups.sort(key=lambda g: g["order"])

    return {"anchor": seen.get(anchor_key), "doc_type": doc_type, "doc_id": doc_id,
            "depth": max_depth, "nodes": nodes, "edges": edges, "groups": groups,
            "node_count": len(nodes), "edge_count": len(edges), "truncated": truncated}


async def reference_line(doc_type: str, doc_id: str, limit: int = 6) -> Dict[str, Any]:
    """Baris "Merujuk: SO-0012 · PR-00021" untuk kop dokumen cetak.

    Urutan sengaja mengutamakan dokumen INDUK (asal-usul) karena itu yang dicari
    pembaca kertas; turunan/pelunasan menyusul bila masih ada tempat.
    """
    try:
        data = await refs_of(doc_type, doc_id, resolve_targets=True)
    except RefsError:
        return {"text": "", "items": []}
    items: List[Dict[str, str]] = []
    for r in data["refs"]:
        num = r.get("doc_number") or ""
        # Dokumen yang sudah tidak ada TIDAK dicetak — kertas tidak boleh menunjuk hantu.
        # Tautan turunan (jurnal/kas) juga tidak dicetak di kop — itu jejak internal.
        if not num or r.get("alive") is False or r.get("derived"):
            continue
        items.append({"rel": r.get("rel", ""), "rel_label": r.get("rel_label", ""),
                      "label": r.get("label", ""), "number": num,
                      "doc_type": r.get("doc_type", ""), "doc_id": r.get("doc_id", "")})
    items.sort(key=lambda x: (0 if x["rel"] in PARENT_RELS else 1,
                              DOC_TYPES.get(x["doc_type"], {}).get("order", 50)))
    seen_num = set()
    uniq = []
    for it in items:
        if it["number"] in seen_num:
            continue
        seen_num.add(it["number"])
        uniq.append(it)
    shown = uniq[: max(1, int(limit or 6))]
    return {"text": " · ".join(x["number"] for x in shown),
            "items": shown, "total": len(uniq), "hidden": max(0, len(uniq) - len(shown))}


# ── Pencarian dokumen (titik masuk layar Jejak Dokumen) ────────────────────
async def search(q: str, limit: int = 20, entity_id: str = "",
                 viewer_perms: Optional[Dict[str, List[str]]] = None) -> List[Dict[str, Any]]:
    """Cari dokumen lintas jenis berdasarkan nomor / nama pihak. PK-17: nominal disaring `redact_node`."""
    ql = (q or "").strip()
    if len(ql) < 2:
        return []
    import re as _re
    rx = _re.compile(_re.escape(ql), _re.I)
    out: List[Dict[str, Any]] = []
    for meta in sorted(DOC_TYPES.values(), key=lambda m: m["order"]):
        if len(out) >= limit:
            break
        flt: Dict[str, Any] = dict(meta["filter"])
        or_clauses: List[Dict[str, Any]] = [
            {meta["number"]: rx}, {"customer_name": rx}, {"supplier_name": rx}]
        flt["$or"] = or_clauses
        if entity_id and entity_id != "all":
            flt["entity_id"] = entity_id
        try:
            rows = await db[meta["collection"]].find(flt, {"_id": 0}).limit(5).to_list(5)
        except Exception:  # noqa: BLE001 — koleksi belum ada di DB baru
            continue
        for row in rows:
            node = redact_node(node_of(meta["doc_type"], safe_doc(row)), viewer_perms)
            node["ref_count"] = len(row.get("refs") or [])
            out.append(node)
    return out[:limit]


# ── Backfill data lama (idempotent, aman diulang) ──────────────────────────
async def _iter(collection: str, flt: Dict[str, Any], fields: Sequence[str]):
    proj = {"_id": 0, "id": 1}
    for f in fields:
        proj[f] = 1
    async for row in db[collection].find(flt, proj):
        yield row


async def backfill(dry_run: bool = True) -> Dict[str, Any]:
    """Bentuk `refs[]` dari kolom penghubung yang SUDAH ada di dokumen lama.

    Tidak mengarang relasi: setiap aturan memakai foreign key nyata yang memang
    dipakai mesin (mis. `shipments.order_id`). Idempotent — menjalankan berkali-kali
    tidak menduplikasi karena `_push_ref` melakukan dedupe.
    """
    plan: List[Dict[str, str]] = []

    async def rule(src_type: str, dst_type: str, rel: str, collection: str,
                   fk: str, flt: Optional[Dict[str, Any]] = None, note: str = "") -> None:
        base = dict(flt or {})
        base[fk] = {"$nin": [None, ""]}
        async for row in _iter(collection, base, [fk]):
            plan.append({"src_type": src_type, "src_id": row["id"], "dst_type": dst_type,
                         "dst_id": row[fk], "rel": rel, "note": note})

    # Rantai pembelian
    # P-0 (2026-08-20) — BUG YANG DITEMUKAN & DITUTUP: baris ini dulu berbunyi
    #     rule("purchase_order", "purchase_requisition", "parent",
    #          "purchase_requisitions", "po_id", ...)
    # yaitu MENGITERASI koleksi PR tetapi mengaku `src_type="purchase_order"`, dan
    # memakai `row["id"]` (id PR!) sebagai id PO sekaligus `row["po_id"]` (id PO)
    # sebagai id PR. Jadi src & dst TERTUKAR, keduanya. Akibatnya `load_doc(
    # "purchase_order", "<id PR>")` selalu None → `link()` mengembalikan
    # `{"linked": 0, "reason": "dokumen tidak ditemukan"}` dan baris itu **di-skip
    # DIAM-DIAM**. Terukur sebelum perbaikan: `backfill(dry_run=True)` →
    # `candidates=74 · would_add=0 · skipped=1`, dan `skipped=1` itu PERSIS baris ini.
    # Artinya rantai PO→PR **tidak pernah sekali pun** ter-backfill sejak dibuat —
    # dan justru rantai inilah prasyarat kolom "Nama Sales" di papan PO (DRIFT D3).
    # Arah yang benar: iterasi `purchase_orders` dengan FK `pr_id` (field kanonik P-0).
    await rule("purchase_order", "purchase_requisition", "parent",
               "purchase_orders", "pr_id", note="PR sumber PO")
    await rule("grn", "purchase_order", "parent", "wms_tasks", "po_id",
               flt={"flow_type": "inbound"}, note="penerimaan dari PO")
    await rule("vendor_bill", "purchase_order", "parent", "vendor_bills", "po_id",
               note="tagihan atas PO")
    await rule("purchase_return", "purchase_order", "reverses", "purchase_returns", "po_id",
               note="retur atas PO")
    await rule("makloon_order", "purchase_order", "parent", "makloon_orders", "po_id")
    await rule("makloon_order", "supplier_contract", "fulfills", "makloon_orders", "contract_id",
               note="kontrak makloon")
    await rule("vendor_bill", "makloon_order", "settles", "vendor_bills", "makloon_order_id",
               note="tagihan jasa makloon")

    # Rantai penjualan
    await rule("sales_order", "special_order", "parent", "sales_orders",
               "source_special_order_id", note="berasal dari Pesanan Khusus")
    await rule("picking_task", "sales_order", "parent", "wms_tasks", "order_id",
               flt={"flow_type": "outbound"}, note="pengambilan untuk SO")
    await rule("shipment", "sales_order", "parent", "shipments", "order_id",
               note="pengiriman atas SO")
    await rule("tax_invoice", "sales_order", "parent", "tax_invoices", "order_id",
               note="faktur atas SO")
    await rule("tax_invoice", "tax_invoice", "replaces", "tax_invoices", "replaces_id",
               note="faktur pengganti")
    await rule("sales_return", "sales_order", "reverses", "sales_returns", "order_id",
               note="retur atas SO")
    await rule("credit_note", "sales_order", "corrects", "credit_notes", "order_id")
    await rule("credit_note", "doc_amendment", "issued_by", "credit_notes", "amendment_id")
    await rule("doc_amendment", "sales_order", "amends", "doc_amendments", "doc_id")
    # FASE G-2 — rencana pembayaran & nota denda menaut dokumen sumbernya.
    await rule("payment_plan", "sales_order", "parent", "payment_plans", "doc_id",
               note="jadwal pembayaran dokumen ini")
    await rule("penalty", "sales_order", "parent", "penalties", "doc_id",
               note="denda keterlambatan")
    # PK-44 (IA-10) — LPJ menaut PD-nya (dokumen lama; LPJ baru ditaut saat lahir di `cash_advance_service`).
    await rule("cash_settlement", "cash_advance", "parent", "cash_advance_settlements", "cash_advance_id",
               note=LPJ_NOTE)

    # Landed cost menaut BANYAK PO (array) — ditangani terpisah.
    async for row in db.landed_cost_vouchers.find({"po_ids": {"$exists": True}},
                                                  {"_id": 0, "id": 1, "po_ids": 1}):
        for poid in row.get("po_ids") or []:
            plan.append({"src_type": "landed_cost", "src_id": row["id"],
                         "dst_type": "purchase_order", "dst_id": poid,
                         "rel": "parent", "note": "biaya masuk untuk PO"})

    # Kwitansi menaut BANYAK order lewat alokasi.
    async for row in db.ar_receipts.find({}, {"_id": 0, "id": 1, "allocations": 1}):
        for alloc in row.get("allocations") or []:
            if alloc.get("order_id"):
                plan.append({"src_type": "ar_receipt", "src_id": row["id"],
                             "dst_type": "sales_order", "dst_id": alloc["order_id"],
                             "rel": "settles", "note": "pembayaran dialokasikan"})

    would, wrote, skipped = 0, 0, 0
    for p in plan:
        if dry_run:
            src = await load_doc(p["src_type"], p["src_id"])
            dst = await load_doc(p["dst_type"], p["dst_id"])
            if not src or not dst:
                skipped += 1
                continue
            have = any(_same(r, p["rel"], p["dst_type"], p["dst_id"])
                       for r in (src.get("refs") or []))
            if not have:
                would += 1
            continue
        res = await link((p["src_type"], p["src_id"]), (p["dst_type"], p["dst_id"]),
                         p["rel"], note=p["note"], force=True)
        wrote += int(res.get("linked", 0))
        if not res.get("linked"):
            skipped += 1

    return {"dry_run": dry_run, "candidates": len(plan), "would_add": would,
            "written": wrote, "skipped": skipped}


# ── Bahan invarian INV-REF (dibaca `scripts/verify_data_integrity.py`) ─────
def _has_source(row: Dict[str, Any], fks: Sequence[str]) -> bool:
    """True bila dokumen memang punya kolom penghubung berisi (lahir dari dokumen lain)."""
    if not fks:
        return True  # tidak ada info FK → tetap wajib menaut (perilaku ketat sebelumnya)
    for f in fks:
        val = row.get(f)
        if isinstance(val, (list, tuple)):
            if any(bool(v) for v in val):
                return True
        elif val not in (None, "", 0):
            return True
    return False


async def orphan_children(limit: int = 50) -> List[Dict[str, Any]]:
    """Dokumen turunan yang TIDAK punya satu pun referensi induk yang hidup.

    Dokumen yang memang berdiri sendiri (tidak punya kolom sumber apa pun — mis.
    penerimaan barang tanpa PO, kwitansi uang muka tanpa alokasi invoice) TIDAK
    dilaporkan yatim: lihat `standalone_children()` untuk angka transparansinya.
    """
    bad: List[Dict[str, Any]] = []
    for meta in DOC_TYPES.values():
        if not meta["needs_parent"]:
            continue
        flt = dict(meta["filter"])
        proj = {"_id": 0, "id": 1, "refs": 1, meta["number"]: 1}
        for f in meta.get("source_fk") or []:
            proj[f] = 1
        async for row in db[meta["collection"]].find(flt, proj):
            if not _has_source(row, meta.get("source_fk") or []):
                continue
            parents = [r for r in (row.get("refs") or [])
                       if r.get("rel") in PARENT_RELS and r.get("doc_id")]
            alive = False
            for p in parents:
                if p.get("doc_type") in DOC_TYPES and await load_doc(p["doc_type"], p["doc_id"]):
                    alive = True
                    break
            if not alive:
                bad.append({"doc_type": meta["doc_type"], "doc_id": row["id"],
                            "number": row.get(meta["number"]) or row["id"]})
                if len(bad) >= limit:
                    return bad
    return bad


async def standalone_children(limit: int = 200) -> List[Dict[str, Any]]:
    """Dokumen turunan yang SAH tanpa induk (tidak punya kolom sumber sama sekali).

    Dilaporkan eksplisit oleh gate & `scripts/audit_doc_refs.py` supaya tidak menjadi
    tempat sembunyi: kalau angka ini melonjak, ada jalur pembuatan dokumen yang lupa
    menyimpan kolom sumbernya.
    """
    out: List[Dict[str, Any]] = []
    for meta in DOC_TYPES.values():
        if not meta["needs_parent"] or not meta.get("source_fk"):
            continue
        flt = dict(meta["filter"])
        proj = {"_id": 0, "id": 1, meta["number"]: 1}
        for f in meta["source_fk"]:
            proj[f] = 1
        async for row in db[meta["collection"]].find(flt, proj):
            if _has_source(row, meta["source_fk"]):
                continue
            out.append({"doc_type": meta["doc_type"], "doc_id": row["id"],
                        "number": row.get(meta["number"]) or row["id"]})
            if len(out) >= limit:
                return out
    return out


async def dangling_refs(limit: int = 50) -> List[Dict[str, Any]]:
    """Tautan yang menunjuk dokumen yang SUDAH TIDAK ADA (jejak menunjuk hantu).

    SATU sumber kebenaran untuk tiga pemakai: `scripts/audit_doc_refs.py` (§C
    kesehatan tautan), `scripts/gate_residue.py --check` (INV-GATE-01), dan
    `scripts/guardrails/verify_ref_unlink.py` (INV-REF-04). Sebelumnya hanya
    `audit_doc_refs` yang memeriksanya dengan salinan kodenya sendiri, dan itu
    membuat satu kelas residu lolos satu putaran penuh: di `gate.sh`,
    `audit_doc_refs` berjalan SEBELUM semua POC (baris ~380 vs ~446), jadi tautan
    hantu yang ditinggalkan sebuah POC baru terlihat pada gate BERIKUTNYA — dan
    pada saat itu tidak ada lagi yang menghubungkannya dengan POC penyebabnya.
    """
    bad: List[Dict[str, Any]] = []
    for meta in DOC_TYPES.values():
        flt = dict(meta["filter"])
        flt["refs.0"] = {"$exists": True}
        proj = {"_id": 0, "id": 1, "refs": 1, meta["number"]: 1}
        async for row in db[meta["collection"]].find(flt, proj):
            for r in row.get("refs") or []:
                t, i = r.get("doc_type"), r.get("doc_id")
                if not t or not i or t not in DOC_TYPES:
                    continue  # doc_type tak dikenal = pemeriksaan lain, bukan hantu
                if await load_doc(t, i):
                    continue
                bad.append({"from": f"{meta['doc_type']}:{row['id']}",
                            "from_number": row.get(meta["number"]) or row["id"],
                            "to": f"{t}:{i}",
                            "to_number": r.get("doc_number") or "",
                            "rel": r.get("rel", "")})
                if len(bad) >= limit:
                    return bad
    return bad


async def unlink_all(doc_type: str, doc_id: str) -> Dict[str, Any]:
    """Sapu SEMUA tautan yang menunjuk dokumen ini — **pasangan wajib `link()`**.

    KENAPA ADA (kelas bug terukur 2026-08-21, bukan dugaan)
    -------------------------------------------------------
    `link()` menulis relasi **dua arah**. Konsekuensinya: siapa pun yang MENGHAPUS
    dokumen wajib menyapu tautan baliknya, kalau tidak dokumen yang MASIH HIDUP
    tetap memegang ref ke dokumen yang sudah tidak ada — dan layar "Relasi
    Dokumen" dengan tenang menawarkan tautan yang menuju 404. Ditemukan lewat
    POC FASE E-7: `internal_requests KSC/PIN-00003` memegang dua ref
    `fulfilled_by` ke draf antar-PT yang sudah dihapus pembersih POC.

    Bukan cuma soal POC. Empat jalur PRODUKSI punya lubang yang sama:
      · `po_amendment_service`   — amandemen PO menghapus inbound `wms_tasks`
                                   (doc_type `grn`) yang sudah bertaut ke PO-nya
      · `purchase_return_service`— hapus retur draf yang sudah menaut PO
      · `routers/supplier_contracts` — hapus kontrak (order makloon menaut lewat
                                   `contract_id` tingkat atas, sedangkan pagar
                                   penghapusan hanya memeriksa `steps.contract_id`)
      · `routers/sales_orders`   — rollback transfer antar-gudang saat SO gagal

    Idempotent & aman dipanggil untuk dokumen yang tidak punya tautan apa pun.
    Dipakai SEBELUM `delete_one/delete_many`. Dijaga statis oleh **INV-REF-04**.
    """
    if not doc_id:
        return {"removed": 0, "collections": []}
    if doc_type not in DOC_TYPES:
        raise RefsError(f"Jenis dokumen '{doc_type}' belum terdaftar di peta relasi.")
    touched: List[str] = []
    removed = 0
    # Iterasi per KOLEKSI (bukan per doc_type): beberapa doc_type berbagi koleksi
    # yang sama, dan `$pull` di bawah sudah presisi karena mencocokkan pasangan
    # (doc_type, doc_id) — jadi menyapu dua kali hanya membuang waktu.
    for coll_name in sorted({m["collection"] for m in DOC_TYPES.values()}):
        res = await db[coll_name].update_many(
            {"refs": {"$elemMatch": {"doc_type": doc_type, "doc_id": doc_id}}},
            {"$pull": {"refs": {"doc_type": doc_type, "doc_id": doc_id}},
             "$set": {"updated_at": now_iso()}})
        if res.modified_count:
            touched.append(f"{coll_name}×{res.modified_count}")
            removed += res.modified_count
    return {"removed": removed, "collections": touched}


async def safe_unlink_all(doc_type: str, doc_id: str) -> None:
    """Versi `unlink_all()` untuk dipasang di jalur transaksi bisnis.

    Sama alasannya dengan `safe_link()`: menyapu jejak adalah pelengkap, bukan
    syarat sahnya penghapusan dokumen. Kegagalan menyapu tidak boleh membuat
    penghapusan yang sah gagal — `audit_doc_refs` / INV-GATE-01 yang akan
    berteriak bila ada hantu tertinggal.
    """
    try:
        await unlink_all(doc_type, doc_id)
    except Exception:  # noqa: BLE001
        return


async def one_way_refs(limit: int = 50) -> List[Dict[str, Any]]:
    """Relasi yang hanya ada di satu sisi (tidak bisa ditelusuri balik)."""
    bad: List[Dict[str, Any]] = []
    for meta in DOC_TYPES.values():
        flt = dict(meta["filter"])
        flt["refs"] = {"$exists": True, "$ne": []}
        async for row in db[meta["collection"]].find(flt, {"_id": 0, "id": 1, "refs": 1}):
            for r in row.get("refs") or []:
                t, i = r.get("doc_type"), r.get("doc_id")
                if not t or not i or t not in DOC_TYPES:
                    continue
                tgt = await load_doc(t, i)
                if not tgt:
                    continue  # target mati → urusan INV-REF-01, bukan dua arah
                back = [b for b in (tgt.get("refs") or [])
                        if b.get("doc_id") == row["id"] and b.get("doc_type") == meta["doc_type"]]
                if not back:
                    bad.append({"from": f"{meta['doc_type']}:{row['id']}",
                                "to": f"{t}:{i}", "rel": r.get("rel", "")})
                    if len(bad) >= limit:
                        return bad
    return bad
