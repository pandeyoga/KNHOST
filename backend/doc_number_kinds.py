"""doc_number_kinds.py — katalog JENIS NOMOR DOKUMEN (unit KP-T5, KP-12 / KP-35).

Satu baris = satu deret nomor yang dibuat `core_utils.next_doc_number`: label untuk manusia, kelompok layar, koleksi dan
field tempat nomor disimpan, **awalan identitas** (awalan hari ini = kunci deret di `number_sequences`; tidak pernah
berubah walau awalan tercetak diubah), dan **bawaan** `{prefix, width, date_token, reset, scope}` = persis bentuk nomor
yang terbit sebelum unit ini dipasang.

Ini STRUKTUR, bukan nilai bisnis: format yang diubah pemilik tersimpan di koleksi `doc_number_formats` (layar Pengaturan ›
Dokumen & Notifikasi › Penomoran Dokumen) dan dibaca `services/doc_numbering_service.effective_format`. Tanpa baris tersimpan,
nomor berikutnya = bawaan katalog = perilaku lama (dibuktikan `tests_mem/test_KPT5a_setara.py` untuk tiap titik panggil).

Aturan:
- `scope`: `per_pt` = `{KODE PT}/{awalan}{sisipan-}{angka}`, deret per (PT, awalan identitas); `bersama` = satu deret untuk
  seluruh grup, `{awalan}{sisipan-}{angka}`. Titik panggil per PT tanpa PT (kosong / `"all"`) tetap memakai deret bersama.
- `clock`: jam sisipan tanggal — `wib`, kecuali `lot` yang sejak awal memakai jam UTC.
- `locked`: tidak bisa diubah dari layar (RFID dekat gerbang — H7; kode master dipakai bersama; nomor turunan).
- `derived`: nomor diturunkan dari dokumen lain (`INV-<nomor SO>-NN`); awalannya dibentuk titik panggil, format tidak diatur.
- `entity_field`: field PT di koleksi itu (semai deret per PT, hitungan dokumen lama); roll memakai `owner_entity_id`.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

#: Kelompok layar (urutan tampil).
GROUPS: Tuple[str, ...] = ("Penjualan", "Pembelian", "Keuangan", "Gudang", "Antar-PT", "R&D", "SDM", "Master")

DATE_TOKENS: Tuple[str, ...] = ("", "YY", "YYYY", "YYMM", "YYYYMM", "YYMMDD")
RESETS: Tuple[str, ...] = ("tidak", "tahunan", "bulanan", "harian")
SCOPES: Tuple[str, ...] = ("per_pt", "bersama")

#: strftime tiap sisipan tanggal.
DATE_FORMAT: Dict[str, str] = {"YY": "%y", "YYYY": "%Y", "YYMM": "%y%m", "YYYYMM": "%Y%m", "YYMMDD": "%y%m%d"}


def _k(kind: str, label: str, group: str, collection: str, field: str, prefix: str, *, width: int = 5,
       scope: str = "per_pt", date_token: str = "", reset: str = "tidak", clock: str = "wib",
       locked: bool = False, derived: bool = False, note: str = "", entity_field: str = "entity_id") -> Dict[str, Any]:
    return {"kind": kind, "label": label, "group": group, "collection": collection, "field": field,
            "identity_prefix": prefix, "entity_field": entity_field,
            "default": {"prefix": prefix, "width": width, "date_token": date_token, "reset": reset, "scope": scope},
            "clock": clock, "locked": locked, "derived": derived, "note": note}


_P, _B = "per_pt", "bersama"

KINDS_LIST: List[Dict[str, Any]] = [
    # ── Penjualan ──────────────────────────────────────────────────────────────────────────────────────────────────
    _k("so", "Pesanan penjualan", "Penjualan", "sales_orders", "number", "SO-"),
    _k("sos", "Pesanan sampel", "Penjualan", "sales_orders", "number", "SOS-"),
    _k("sj", "Surat jalan", "Penjualan", "shipments", "shipment_no", "SJ-"),
    _k("cn", "Nota kredit", "Penjualan", "credit_notes", "number", "CN-",
       note="Amandemen dan batal item pesanan."),
    _k("dn", "Nota debit", "Penjualan", "credit_notes", "number", "DN-", note="Amandemen pesanan yang menambah tagihan."),
    _k("amd", "Amandemen dokumen", "Penjualan", "doc_amendments", "number", "AMD-"),
    _k("sret", "Retur penjualan", "Penjualan", "sales_returns", "number", "SRET-", scope=_B),
    _k("cn_retur", "Nota kredit retur", "Penjualan", "credit_notes", "number", "CN-", scope=_B),
    _k("scr", "Pemakaian saldo kredit pelanggan", "Penjualan", "store_credit_redemptions", "number", "SCR-"),
    _k("cf", "Masukan pelanggan", "Penjualan", "customer_feedbacks", "number", "CF-"),
    _k("pin", "Permintaan internal", "Penjualan", "internal_requests", "number", "PIN-"),
    _k("sord", "Pesanan khusus", "Penjualan", "special_orders", "number", "SORD-", width=4, scope=_B,
       date_token="YYMMDD", reset="harian"),
    _k("inv", "Faktur penjualan", "Penjualan", "invoices", "number", "INV-", width=2, scope=_B, locked=True,
       derived=True, note="Diturunkan dari nomor pesanan (INV-<nomor pesanan>-01)."),
    # ── Pembelian & produksi ───────────────────────────────────────────────────────────────────────────────────────
    _k("po", "Pesanan pembelian", "Pembelian", "purchase_orders", "po_number", "PO-"),
    _k("pr", "Permintaan pembelian", "Pembelian", "purchase_requisitions", "number", "PR-", scope=_B),
    _k("rfq", "Permintaan penawaran", "Pembelian", "rfqs", "rfq_number", "RFQ-", scope=_B),
    _k("pret", "Retur pembelian", "Pembelian", "purchase_returns", "number", "PRET-", scope=_B),
    _k("dn_retur_beli", "Nota debit retur pembelian", "Pembelian", "purchase_returns", "debit_note_number", "DN-",
       scope=_B),
    _k("vb", "Tagihan pemasok", "Pembelian", "vendor_bills", "bill_number", "VB-", scope=_B),
    _k("vbm", "Tagihan jasa makloon", "Pembelian", "vendor_bills", "bill_number", "VBM-", scope=_B),
    _k("lcv", "Biaya tambahan pembelian", "Pembelian", "landed_cost_vouchers", "voucher_number", "LCV-", scope=_B),
    _k("sct", "Kontrak pemasok", "Pembelian", "supplier_contracts", "contract_number", "SCT-"),
    _k("mko", "SPK makloon", "Pembelian", "makloon_orders", "mko_number", "MKO-",
       note="Tanpa PT (data lama/uji) memakai deret bersama."),
    _k("wo", "Perintah kerja produksi", "Pembelian", "mfg_work_orders", "wo_number", "WO-", scope=_B),
    # ── Keuangan ───────────────────────────────────────────────────────────────────────────────────────────────────
    _k("fkt", "Faktur pajak keluaran", "Keuangan", "tax_invoices", "number", "FKT-"),
    _k("fpm", "Faktur pajak masukan", "Keuangan", "tax_invoices_in", "number", "FPM-", scope=_B),
    _k("ar", "Penerimaan piutang", "Keuangan", "ar_receipts", "number", "AR-"),
    _k("cash", "Transaksi kas dan bank", "Keuangan", "cash_transactions", "number", "CASH-"),
    _k("je", "Jurnal", "Keuangan", "journal_entries", "number", "JE-"),
    _k("cb", "Kontrabon", "Keuangan", "contra_bons", "number", "CB-"),
    _k("rpb", "Rencana pembayaran", "Keuangan", "payment_plans", "number", "RPB-"),
    _k("slb", "Keputusan selisih bayar", "Keuangan", "payment_variance_decisions", "number", "SLB-"),
    _k("denda", "Nota denda", "Keuangan", "penalties", "number", "DN-DENDA-"),
    _k("case", "Kasus keuangan", "Keuangan", "finance_cases", "number", "CASE-"),
    _k("fa", "Aset tetap", "Keuangan", "fin_fixed_assets", "number", "FA-"),
    _k("pd", "Uang muka karyawan", "Keuangan", "cash_advances", "number", "PD-"),
    _k("stl", "Pertanggungjawaban uang muka", "Keuangan", "cash_advance_settlements", "number", "STL-"),
    _k("mcc", "Biaya kampanye pemasaran", "Keuangan", "mkt_campaign_costs", "number", "MCC-"),
    # CR-T1 — pengajuan perubahan profil kredit pelanggan (per PT pesanan).
    _k("pkr", "Pengajuan perubahan kredit", "Keuangan", "credit_profile_requests", "number", "PKR-"),
    # ── Gudang ─────────────────────────────────────────────────────────────────────────────────────────────────────
    _k("trf", "Mutasi gudang", "Gudang", "warehouse_transfers", "code", "TRF-"),
    _k("grn", "Penerimaan barang", "Gudang", "goods_receipts", "number", "GRN-"),
    _k("ins", "Inspeksi mutu", "Gudang", "inspections", "number", "INS-"),
    _k("reg", "Registrasi awal stok", "Gudang", "cycle_count_sessions", "number", "REG-"),
    _k("lot", "Nomor lot", "Gudang", "inventory_lots", "lot_number", "LOT-", width=4, date_token="YYMM",
       reset="bulanan", clock="utc"),
    _k("rtn", "Roll hasil retur", "Gudang", "inventory_rolls", "roll_no", "RTN-", scope=_B,
       entity_field="owner_entity_id"),
    _k("rpr", "Perintah perbaikan", "Gudang", "repair_orders", "number", "RPR-"),
    _k("lg", "Pengiriman logistik", "Gudang", "logistics_deliveries", "number", "LG-"),
    _k("vhl", "Catatan pemakaian kendaraan", "Gudang", "vehicle_usage_logs", "number", "VHL-"),
    _k("cc", "Hitung stok RFID", "Gudang", "rfid_cycle_counts", "cc_number", "CC", scope=_B, locked=True),
    _k("btg", "Kedatangan barang RFID", "Gudang", "putaway_orders", "btg_number", "BTG", scope=_B, locked=True),
    _k("pa", "Perintah simpan barang", "Gudang", "putaway_orders", "pa_number", "PA", scope=_B, locked=True),
    _k("pj", "Tugas cetak label RFID", "Gudang", "rfid_print_jobs", "job_number", "PJ", scope=_B, locked=True),
    # ── Antar-PT ───────────────────────────────────────────────────────────────────────────────────────────────────
    _k("ic", "Transaksi antar-PT", "Antar-PT", "interco_transactions", "number", "IC-"),
    _k("ics", "Pelunasan antar-PT", "Antar-PT", "interco_settlements", "number", "ICS-"),
    _k("icl", "Pinjaman antar-PT", "Antar-PT", "interco_loans", "number", "ICL-"),
    _k("icr", "Retur antar-PT", "Antar-PT", "interco_returns", "number", "ICR-"),
    # ── R&D ────────────────────────────────────────────────────────────────────────────────────────────────────────
    _k("dsr", "Permintaan desain", "R&D", "design_requests", "number", "DSR-"),
    _k("smp", "Sampel", "R&D", "md_samples", "number", "SMP-"),
    _k("spec", "Spesifikasi produk", "R&D", "md_specs", "number", "SPEC-"),
    # ── SDM ────────────────────────────────────────────────────────────────────────────────────────────────────────
    _k("lv", "Pengajuan cuti", "SDM", "hr_leave_requests", "number", "LV-"),
    _k("ot", "Pengajuan lembur", "SDM", "hr_overtime", "number", "OT-"),
    _k("pay", "Penggajian", "SDM", "hr_payroll_runs", "number", "PAY-"),
    _k("slip", "Slip gaji", "SDM", "hr_payslips", "number", "SLIP-"),
    _k("emp", "Kode karyawan", "SDM", "hr_employees", "code", "EMP-", scope=_B),
    # ── Master ─────────────────────────────────────────────────────────────────────────────────────────────────────
    _k("sup", "Kode pemasok", "Master", "suppliers", "code", "SUP-", scope=_B, locked=True),
    _k("mak", "Kode makloon", "Master", "makloons", "code", "MAK-", scope=_B, locked=True),
    _k("cust", "Kode pelanggan", "Master", "customers", "code", "CUST-", width=4, scope=_B, locked=True),
]

KINDS: Dict[str, Dict[str, Any]] = {k["kind"]: k for k in KINDS_LIST}
assert len(KINDS) == len(KINDS_LIST), "kind kembar di katalog nomor"

#: Pesan untuk jenis terkunci (layar & server).
LOCKED_NOTE = "Tidak bisa diubah: dipakai bersama atau diturunkan dari dokumen lain."

# Pengenal awalan bersisipan tanggal yang dibentuk titik panggil (mis. `LOT-2611-`, `SORD-261113-`).
_DATED_RE = re.compile(r"^(?P<base>.*?-)(?P<stamp>\d{2,8})-?$")


def kind(k: str) -> Dict[str, Any]:
    if k not in KINDS:
        raise KeyError(k)
    return KINDS[k]


def lookup(collection: str, field: str, prefix: str, scheme: str = "per_entity_prefix",
           kind_hint: str = "") -> Optional[Tuple[Dict[str, Any], Optional[str]]]:
    """Jenis nomor untuk argumen titik panggil `next_doc_number` → `(entri, sisipan)` atau `None` (tidak dikenal).

    `sisipan` = sisipan tanggal yang sudah dirakit titik panggil di awalan (mis. `"2611"` dari `LOT-2611-`), selain itu
    `None`. Bila satu awalan dipakai dua jenis pada koleksi+field yang sama (`CN-`: amandemen per PT vs retur bersama),
    `scheme="shared"` memilih jenis bersama."""
    if kind_hint:
        k = KINDS.get(kind_hint)
        if k is None or k["collection"] != collection or k["field"] != field:
            return None
        if prefix == k["identity_prefix"]:
            return k, None
        m = _DATED_RE.match(prefix or "")
        if k["default"]["date_token"] and m and m.group("base") == k["identity_prefix"]:
            return k, m.group("stamp")
        if k["derived"] and (prefix or "").startswith(k["identity_prefix"]):
            return k, None
        return None
    same = [k for k in KINDS_LIST if k["collection"] == collection and k["field"] == field]
    exact = [k for k in same if k["identity_prefix"] == prefix]
    if len(exact) > 1:
        want = _B if scheme == "shared" else _P
        exact = [k for k in exact if k["default"]["scope"] == want] or exact[:1]
    if exact:
        return exact[0], None
    m = _DATED_RE.match(prefix or "")
    if m:
        for k in same:
            tok = k["default"]["date_token"]
            if tok and m.group("base") == k["identity_prefix"] and len(m.group("stamp")) == len(tok):
                return k, m.group("stamp")
    for k in same:
        if k["derived"] and (prefix or "").startswith(k["identity_prefix"]):
            return k, None
    return None
