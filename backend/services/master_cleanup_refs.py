"""PREP-A — data rujukan lembar perbaikan master produk (hanya MEMBACA).

* `open_docs_by_product` — dokumen TERBUKA yang memakai produk (SO, PO, PR, MKO, transfer, putaway, …).
  Dokumen terbuka memblokir GANTI_KODE / GABUNG_KE / NONAKTIFKAN (K-OPN-06: "dokumen terbuka berkode
  lama diselesaikan/dialihkan dulu"). Satu query per koleksi (status belum selesai), dibatasi.
* `stock_by_product` — ringkasan stok lama dari `inventory_balances` (roll + qty, per gudang).
  Hanya referensi/pembanding (K-OPN-01) — stok TIDAK dipindah oleh perbaikan master.
* `duplicate_groups` — kelompok calon duplikat: atribut kanonik `CANON_KEY` sama ATAU nama sama sesudah
  normalisasi (huruf/spasi/tanda baca) ATAU nama berbeda satu huruf (typo) pada atribut inti yang sama.
  Standar penamaan TIDAK dikarang; ini saran, keputusan tetap di kolom `tindakan`.
"""
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from db import db
from services.alert_ops_service import SO_CLOSED_STATUSES
from services.master_governance_service import CANON_KEY

DOC_LIMIT = 5000          # dokumen terbuka per koleksi (cukup untuk operasional; lebih → ditandai terpotong)
EXAMPLES = 5              # nomor dokumen yang disebut per produk

_BASE_CLOSED = {"done", "completed", "closed", "cancelled", "canceled", "rejected", "void", "voided", "archived",
                "expired", "finished", "settled", "paid", "posted", "reversed"}
# (koleksi, field nomor berurutan, label, path product_id, status selesai[, memblokir])
OPEN_DOC_SOURCES: List[Tuple[Any, ...]] = [
    ("sales_orders", ("number",), "SO", ("items.product_id",), _BASE_CLOSED | set(SO_CLOSED_STATUSES)),
    ("purchase_orders", ("po_number", "number"), "PO", ("items.product_id",), _BASE_CLOSED | {"closed_short"}),
    ("purchase_requisitions", ("number",), "PR", ("items.product_id",), _BASE_CLOSED | {"converted"}),
    ("makloon_orders", ("mko_number", "number"), "Order Makloon",
     ("material_product_id", "final_output_product_id", "items.product_id", "steps.input_product_id",
      "steps.output_product_id", "steps.byproduct_product_id"), _BASE_CLOSED),
    ("material_reservations", ("mko_number", "number"), "Cadangan bahan MKO", ("product_id", "output_product_id"),
     _BASE_CLOSED | {"consumed", "released"}),
    ("warehouse_transfers", ("code", "number"), "Transfer gudang", ("items.product_id",), _BASE_CLOSED | {"received"}),
    ("putaway_orders", ("pa_number", "number"), "Putaway", ("items.product_id",), _BASE_CLOSED),
    ("internal_requests", ("number",), "Permintaan internal", ("items.product_id",),
     _BASE_CLOSED | {"converted", "fulfilled"}),
    ("interco_transactions", ("number",), "Transaksi antar-PT", ("items.product_id",), _BASE_CLOSED),
    ("purchase_returns", ("number",), "Retur pembelian", ("items.product_id",), _BASE_CLOSED),
    ("sales_returns", ("number",), "Retur penjualan", ("items.product_id",),
     _BASE_CLOSED | {"credit_settled", "nego_settled", "refunded"}),
    ("goods_receipts", ("number",), "Penerimaan barang", ("lines.target.product_id", "items.product_id"),
     _BASE_CLOSED),
    ("wms_tasks", ("number", "po_number", "order_number", "id"), "Tugas gudang", ("product_id",),
     _BASE_CLOSED | {"dispatched", "qc_rejected"}),
    ("inspections", ("number",), "SPK inspeksi", ("lines.product_id",), _BASE_CLOSED),
    ("md_samples", ("number",), "Sample R&D", ("product_id",), _BASE_CLOSED | {"decided"}),
    ("rfqs", ("number", "rfq_number"), "RFQ", ("items.product_id",), _BASE_CLOSED | {"awarded"}),
    ("repair_orders", ("number", "ro_number"), "Order perbaikan",
     ("product_id", "target_product_id", "items.product_id"), _BASE_CLOSED),
    # Kontrak supplier/jasa = dokumen jangka panjang: TIDAK memblokir, hanya diingatkan untuk diperbarui.
    ("supplier_contracts", ("contract_number", "number"), "Kontrak supplier", ("product_id", "input_product_id"),
     _BASE_CLOSED | {"terminated", "expired"}, False),
]


def _values(doc: Any, path: str) -> Iterable[Any]:
    """Nilai pada path bertitik; menembus list (items.product_id, lines.target.product_id)."""
    head, _, rest = path.partition(".")
    if isinstance(doc, list):
        for d in doc:
            yield from _values(d, path)
        return
    if not isinstance(doc, dict):
        return
    val = doc.get(head)
    if not rest:
        if isinstance(val, list):
            yield from val
        elif val:
            yield val
    elif val is not None:
        yield from _values(val, rest)


async def open_docs_by_product(product_ids: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """{"by_product": {pid: [{"label","number","status","collection","blocking"}]}, "truncated": [koleksi]}."""
    ids = set(product_ids) if product_ids is not None else None
    by_product: Dict[str, List[Dict[str, str]]] = {}
    truncated: List[str] = []
    if ids is not None and not ids:
        return {"by_product": by_product, "truncated": truncated}
    for coll, num_fields, label, paths, closed, *flag in OPEN_DOC_SOURCES:
        blocking = flag[0] if flag else True
        q: Dict[str, Any] = {"status": {"$nin": sorted(closed)}}
        if ids is not None:
            q["$or"] = [{p: {"$in": sorted(ids)}} for p in paths]
        proj = {"_id": 0, "status": 1, **{f: 1 for f in num_fields}, **{p.split(".")[0]: 1 for p in paths}}
        rows = await db[coll].find(q, proj).limit(DOC_LIMIT).to_list(DOC_LIMIT)
        if len(rows) >= DOC_LIMIT:
            truncated.append(coll)
        for d in rows:
            number = next((str(d[f]) for f in num_fields if d.get(f)), "") or "(tanpa nomor)"
            pids = {v for p in paths for v in _values(d, p) if isinstance(v, str)}
            for pid in pids if ids is None else pids & ids:
                by_product.setdefault(pid, []).append(
                    {"label": label, "number": number, "status": str(d.get("status") or ""), "collection": coll,
                     "blocking": blocking})
    return {"by_product": by_product, "truncated": truncated}


def docs_text(docs: List[Dict[str, str]], limit: int = EXAMPLES) -> str:
    """"SO KSC/SO-0001, PO KSC/PO-0002 (+3 lagi)"."""
    head = ", ".join(f"{d['label']} {d['number']}" for d in docs[:limit])
    return head + (f" (+{len(docs) - limit} lagi)" if len(docs) > limit else "")


async def stock_by_product(product_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """{pid: {"rolls", "qty", "per_warehouse": [{"code","rolls","qty"}]}} dari inventory_balances."""
    ids = sorted(set(product_ids))
    if not ids:
        return {}
    wh = {w["id"]: (w.get("code") or w.get("name") or w["id"]) for w in await db.warehouses.find(
        {}, {"_id": 0, "id": 1, "code": 1, "name": 1}).to_list(2000)}
    rows = await db.inventory_balances.aggregate([
        {"$match": {"product_id": {"$in": ids}}},
        {"$group": {"_id": {"p": "$product_id", "w": "$warehouse_id"},
                    "qty": {"$sum": {"$ifNull": ["$on_hand_qty", 0]}},
                    "rolls": {"$sum": {"$ifNull": ["$on_hand_roll_count", 0]}}}},
    ]).to_list(20000)
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        qty, rolls = float(r.get("qty") or 0), int(r.get("rolls") or 0)
        if abs(qty) < 1e-9 and not rolls:
            continue
        s = out.setdefault(r["_id"]["p"], {"rolls": 0, "qty": 0.0, "per_warehouse": []})
        s["rolls"] += rolls
        s["qty"] = round(s["qty"] + qty, 2)
        s["per_warehouse"].append({"code": wh.get(r["_id"]["w"], r["_id"]["w"] or "-"), "rolls": rolls,
                                   "qty": round(qty, 2)})
    for s in out.values():
        s["per_warehouse"].sort(key=lambda x: -x["qty"])
    return out


# ─── calon duplikat ───────────────────────────────────────────────────────────
def norm_name(name: Any) -> str:
    """Huruf kecil, aksen dibuang, tanda baca & spasi dihapus: "Alice  Knit (94139-45)" → "aliceknit9413945"."""
    s = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def one_edit_apart(a: str, b: str) -> bool:
    """True bila a dan b berbeda TEPAT satu sisip/hapus/ganti huruf (typo sederhana)."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = j = diff = 0
    while i < len(a) and j < len(b):
        if a[i] != b[j]:
            diff += 1
            if diff > 1:
                return False
            if len(a) == len(b):
                i += 1
            j += 1
            continue
        i += 1
        j += 1
    return diff + (len(b) - j) + (len(a) - i) == 1


def _bucket(p: Dict[str, Any]) -> Tuple[str, ...]:
    """Atribut inti yang WAJIB sama agar dua nama mirip dianggap duplikat."""
    return tuple(str(p.get(k) or "").strip().lower() for k in ("stage", "fabric_type", "color_code", "grade", "base_unit"))


def duplicate_groups(products: List[Dict[str, Any]], usage: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
    """{pid: {"group": "D-001", "reasons": [...], "parent_sku": "...", "is_parent": bool, "size": n}}."""
    parent = {p["id"]: p["id"] for p in products}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    reasons: Dict[str, Set[str]] = {}

    def join(a: str, b: str, why: str) -> None:
        reasons.setdefault(a, set()).add(why)
        reasons.setdefault(b, set()).add(why)
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    canon: Dict[Tuple, str] = {}
    for p in products:
        key = tuple(str(p.get(k) or "") for k in CANON_KEY)
        if not p.get("color_code"):   # tanpa kode warna: nama warna ikut kunci (BLACK ≠ OLIVE)
            key += ("warna:" + norm_name(p.get("color_name") or p.get("color")),)
        if all(key[1:4]):        # stage, fabric_type, line_code terisi (sama dengan preview tata kelola)
            if key in canon:
                join(canon[key], p["id"], "atribut kanonik sama")
            else:
                canon[key] = p["id"]
    buckets: Dict[Tuple, List[Dict[str, Any]]] = {}
    for p in products:
        buckets.setdefault(_bucket(p), []).append(p)
    for rows in buckets.values():
        names = [(p["id"], norm_name(p.get("name"))) for p in rows]
        by_norm: Dict[str, str] = {}
        for pid, n in names:
            if not n:
                continue
            if n in by_norm:
                join(by_norm[n], pid, "nama sama sesudah normalisasi huruf/spasi/tanda baca")
            else:
                by_norm[n] = pid
        # typo hanya di HURUF: angka (kode warna/nomor artikel) wajib sama persis — "KAIN 120" ≠ "KAIN 121"
        uniq = [(pid, n, re.findall(r"[0-9]+", n)) for n, pid in by_norm.items() if len(n) >= 6]
        if len(uniq) > 400:      # batas O(n²) per kelompok atribut inti
            continue
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                if uniq[i][2] == uniq[j][2] and one_edit_apart(uniq[i][1], uniq[j][1]):
                    join(uniq[i][0], uniq[j][0], "nama beda satu huruf (dugaan typo)")
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for p in products:
        groups.setdefault(find(p["id"]), []).append(p)
    out: Dict[str, Dict[str, Any]] = {}
    n = 0
    for members in sorted((g for g in groups.values() if len(g) > 1), key=lambda g: min(x.get("sku", "") for x in g)):
        n += 1
        best = sorted(members, key=lambda x: (
            x.get("status", "active") != "active", bool(x.get("superseded_by")), -usage.get(x["id"], 0),
            x.get("catalog_version") != 2, str(x.get("created_at") or "9999"), str(x.get("sku") or "")))[0]
        for m in members:
            out[m["id"]] = {"group": f"D-{n:03d}", "reasons": sorted(reasons.get(m["id"], set())),
                            "parent_sku": best.get("sku", ""), "is_parent": m["id"] == best["id"],
                            "size": len(members)}
    return out
