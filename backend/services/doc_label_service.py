"""doc_label_service — NOMOR DOKUMEN yang layak dibaca untuk pasangan (jenis sumber daya, id teknis).

Fase 4 · R6 (sisa audit UI tahap 2, G5-01/G5-02). Jejak Audit dan layar Cek Peran dulu hanya bisa menyebut
"Pesanan penjualan" atau — lebih buruk — id teknis `so_3ee0456e1a42`, karena baris `audit_logs` menyimpan
`entity_type`/`entity_id` (sumber daya) dan nomor dokumen hanya ada bila kebetulan ikut di `after`/`details`.
Layar menyembunyikan id teknis itu, sehingga orang kehilangan jawaban "dokumen yang mana?".

Modul ini SATU tempat untuk menerjemahkan pasangan itu ke nomor/nama yang bisa dibaca:
  * nomor diambil dulu dari isi baris (`number`, `po_number`, … di `after`/`before`/`details`) — tanpa query;
  * sisanya dicari **berkelompok** (satu query per koleksi untuk seluruh halaman, tanpa N+1);
  * jenis → koleksi memakai peta dokumen `doc_refs_service.DOC_TYPES` (satu sumber) + peta kecil untuk master
    (pengguna, pelanggan, produk, gudang, …) yang labelnya NAMA, bukan nomor;
  * dokumen yang sudah dihapus → tidak berlabel (layar tetap tidak menampilkan id teknis).
Tidak pernah melempar: label adalah pelengkap tampilan, bukan syarat layar.
"""
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from db import db

#: Field label, urut prioritas. Nomor dokumen dulu, nama master belakangan.
NUMBER_FIELDS: Tuple[str, ...] = (
    "number", "order_number", "po_number", "mko_number", "bill_number", "contract_number", "shipment_no",
    "doc_number", "job_number", "pa_number", "roll_no", "code", "short_name", "name", "label", "title", "key",
)
#: Field nomor yang boleh dibaca langsung dari isi baris audit (`after`/`before`/`details`).
PAYLOAD_FIELDS: Tuple[str, ...] = ("number", "mko_number", "bill_number", "contract_number", "shipment_no")
#: `order_number`/`po_number` di isi baris adalah nomor DOKUMEN ITU sendiri hanya untuk pesanan/PO — untuk jenis
#: lain (mis. retur, tugas gudang) field itu menunjuk dokumen INDUK, jadi tidak dipakai sebagai nomornya.
OWN_ORDER_FIELD: Dict[str, str] = {
    "sales_order": "order_number", "sales_orders": "order_number", "order": "order_number",
    "purchase_order": "po_number", "purchase_orders": "po_number",
}

#: Jenis sumber daya (nilai `entity_type`/`resource` di audit) → koleksi, untuk yang tidak tercakup
#: `DOC_TYPES` dan tidak bernama sama dengan koleksinya.
EXTRA_COLLECTIONS: Dict[str, str] = {
    "user": "users", "customer": "customers", "product": "products", "supplier": "suppliers",
    "warehouse": "warehouses", "warehouse_site": "warehouse_sites", "wms_task": "wms_tasks",
    "inventory_roll": "inventory_rolls", "custom_role": "custom_roles", "price_approval": "price_approvals",
    "product_template": "product_templates", "transfer": "warehouse_transfers", "hr_employee": "hr_employees",
    "bank_account": "bank_accounts", "entity_price": "entity_prices", "makloon": "makloons",
    "mkt_post": "mkt_posts", "mkt_campaign": "mkt_campaigns", "ic_elimination": "intercompany_eliminations",
    "business_entity": "business_entities", "uom": "uoms", "document_template": "document_templates",
    "input_tax": "tax_invoices_in", "design_category": "design_categories", "md_spec": "md_specs",
    "logistics_delivery": "logistics_deliveries", "leave_request": "hr_leave_requests",
    "payroll_run": "hr_payroll_runs",
}

#: Master yang lebih dikenali dari NAMANYA daripada kodenya (pelanggan "Toko Kain Sejahtera", bukan "CUST-0001").
NAME_FIRST = {"user", "customer", "customers", "supplier", "suppliers", "product", "products", "warehouse",
              "warehouses", "warehouse_site", "makloon", "hr_employee", "bank_account", "product_template",
              "custom_role", "mkt_campaign", "business_entity"}

_TECH_ID = re.compile(r"^[a-z][a-z0-9]*_[a-z0-9_]+$")
#: id yang SUDAH berupa kode manusiawi (kode akun `1-1100`, `9-KSC-4667`, grade `Q1`) — boleh tampil apa adanya.
_HUMAN_CODE = re.compile(r"^(?=.*\d)[A-Z0-9][A-Za-z0-9/._-]{1,40}$")


def is_tech_id(value: Any) -> bool:
    """`so_3ee0456e1a42`, `cr_uji_qc_e4c4d6` → True; `KSC/SO-00012`, `9-KSC-4667` → False."""
    return bool(value) and isinstance(value, str) and bool(_TECH_ID.match(value))


def number_from_payload(kind: str, *payloads: Any) -> str:
    """Nomor dokumen yang sudah ada di isi baris (tanpa query). '' bila tidak ada."""
    fields = PAYLOAD_FIELDS + ((OWN_ORDER_FIELD[kind],) if kind in OWN_ORDER_FIELD else ())
    for p in payloads:
        if not isinstance(p, dict):
            continue
        for f in fields:
            v = p.get(f)
            if isinstance(v, str) and v.strip() and not is_tech_id(v.strip()):
                return v.strip()
    return ""


def _collections_for(kind: str, existing: Iterable[str]) -> List[str]:
    """Kandidat koleksi untuk satu jenis sumber daya (urut keyakinan, hanya yang ada di DB)."""
    from services.doc_refs_service import DOC_TYPES
    have = set(existing)
    out: List[str] = []
    meta = DOC_TYPES.get(kind)
    for c in ((meta or {}).get("collection"), EXTRA_COLLECTIONS.get(kind), kind, f"{kind}s"):
        if c and c in have and c not in out:
            out.append(c)
    return out


def _label_of(kind: str, coll: str, doc: Dict[str, Any]) -> str:
    if coll == "wms_tasks":
        # Tugas gudang tidak punya nomor manusiawi — pakai nomor turunan yang sama dengan dokumen cetak
        # (`doc_refs_service.number_of`: GRN-XXXXXX / PICK-XXXXXX).
        from services.doc_refs_service import number_of
        return number_of("grn" if doc.get("flow_type") == "inbound" else "picking_task", doc)
    from services.doc_refs_service import DOC_TYPES
    first = ("short_name", "name", "title") if kind in NAME_FIRST else (
        (DOC_TYPES.get(kind) or {}).get("number") or "number",)
    for f in first + NUMBER_FIELDS:
        v = doc.get(f)
        if isinstance(v, (str, int, float)) and str(v).strip() and f != "id":
            s = str(v).strip()
            if not is_tech_id(s):
                return s
    return ""


async def resolve_labels(pairs: Iterable[Tuple[str, str]]) -> Dict[Tuple[str, str], str]:
    """{(jenis, id): label} untuk pasangan yang id-nya teknis. Berkelompok per koleksi; tidak melempar."""
    want: Dict[str, set] = {}
    for kind, rid in pairs:
        if kind and is_tech_id(rid):
            want.setdefault(str(kind), set()).add(str(rid))
    if not want:
        return {}
    out: Dict[Tuple[str, str], str] = {}
    try:
        existing = await db.list_collection_names()
    except Exception:  # noqa: BLE001 — label pelengkap; DB tak terjangkau → tanpa label
        return out
    proj = {"_id": 0, "id": 1, "flow_type": 1, **{f: 1 for f in NUMBER_FIELDS}}
    from services.doc_refs_service import DOC_TYPES
    for kind, ids in want.items():
        pending = set(ids)
        extra_field = (DOC_TYPES.get(kind) or {}).get("number")
        p = dict(proj, **({extra_field: 1} if extra_field and extra_field != "id" else {}))
        for coll in _collections_for(kind, existing):
            if not pending:
                break
            try:
                async for doc in db[coll].find({"id": {"$in": list(pending)}}, p):
                    label = _label_of(kind, coll, doc)
                    if label:
                        out[(kind, doc["id"])] = label
                    pending.discard(doc.get("id"))
            except Exception:  # noqa: BLE001, S112 — koleksi tak terbaca → coba kandidat berikutnya
                continue
    return out


async def attach_doc_numbers(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tambahkan `doc_number` pada baris `audit_logs` (in-place). Dua bentuk baris dibaca:
    runtime (`entity_type`/`entity_id`/`after`/`before`) dan seed lama (`resource`/`resource_id`/`details`)."""
    need: List[Tuple[str, str]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        kind = str(r.get("entity_type") or r.get("resource") or "")
        rid = str(r.get("entity_id") or r.get("resource_id") or "")
        num = r.get("doc_number") or number_from_payload(kind, r.get("after"), r.get("before"), r.get("details"))
        if num:
            r["doc_number"] = num
        elif is_tech_id(rid):
            need.append((kind, rid))
        elif _HUMAN_CODE.match(rid):
            # id sudah berupa kode manusiawi (mis. kode akun `1-1100`) → itulah labelnya.
            r["doc_number"] = rid
    labels = await resolve_labels(need) if need else {}
    for r in rows:
        if not isinstance(r, dict) or r.get("doc_number"):
            continue
        kind = str(r.get("entity_type") or r.get("resource") or "")
        rid = str(r.get("entity_id") or r.get("resource_id") or "")
        label = labels.get((kind, rid))
        if label:
            r["doc_number"] = label
    return rows


async def label_for(kind: str, rid: str) -> Optional[str]:
    """Satu label (untuk pemanggil tunggal). None bila tak dikenal."""
    if not is_tech_id(rid):
        return rid or None
    return (await resolve_labels([(kind, rid)])).get((kind, rid))
