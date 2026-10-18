"""R0 — Return Policy Engine (Master Data).

Fondasi modul retur (R0 dari RETURNS_ANALYSIS.md §K). Bertanggung jawab atas:

- **Supplier return policy** (embedded di `suppliers.return_policy`) + klasifikasi
  asal barang `origin_type` (local|import) + override per-PO (`import_flag`).
- **Sales return policy** (koleksi `sales_return_policies`, prefix `srp_`) —
  aturan berdiri sendiri dengan scope global / category / customer.
- **Deadline derivation** (linked): `return_deadline = tgl_referensi + window_days`.
- **Eligibility check** untuk retur jual (blok/peringatan bila di luar window).
- **Snapshot policy** ke dokumen retur agar auditable.

Fungsi murni-orchestration (async I/O ke DB), tanpa JSX/HTTP — mudah diuji.
Semua tanggal disimpan/dihitung sebagai ISO-8601 string (kontrak KN3).
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta

from db import db
from core_utils import now_iso

# Mode refund retur BELI (KN → supplier)
SUPPLIER_REFUND_MODES = ("cash", "ap_credit", "none")
ORIGIN_TYPES = ("local", "import")

# Default cerdas untuk kebijakan retur supplier bila belum diisi.
DEFAULT_SUPPLIER_POLICY: Dict[str, Any] = {
    "window_days": 30,
    "refund_modes": ["ap_credit"],
    "returnable_to_supplier": True,
    "rma_required": False,
    "restocking_fee_pct": 0.0,
    "condition_requirements": "",
    "custom_fields": {},
    "valid_from": "",
    "valid_until": "",
    "notes": "",
}

# Default kebijakan retur jual (dipakai bila tak ada policy match sama sekali).
DEFAULT_SALES_POLICY: Dict[str, Any] = {
    "id": "",
    "name": "Default (sistem)",
    "scope": "global",
    "scope_ref": "",
    "window_days": 30,
    "allowed_return_types": ["retur", "bs", "penggantian", "komplain", "garansi"],
    "allowed_outcomes": ["refund", "store_credit", "nego", "reject"],
    "restocking_fee_pct": 0.0,
    "require_inspection": True,
    "enforce_window": False,
    "link_to_supplier_window": False,
    "condition_requirements": "",
    "custom_fields": {},
    "is_default": True,
}


# ─── Util tanggal ────────────────────────────────────────────────────────────

def parse_dt(value: Any) -> Optional[datetime]:
    """Parse ISO string → datetime tz-aware (UTC). None bila gagal/kosong."""
    if not value:
        return None
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except (ValueError, TypeError):
        return None


def compute_deadline(base_date: Any, window_days: int) -> str:
    """Hitung deadline = base_date + window_days (ISO). "" bila base_date invalid."""
    base = parse_dt(base_date)
    if not base:
        return ""
    try:
        wd = int(window_days or 0)
    except (ValueError, TypeError):
        wd = 0
    return (base + timedelta(days=wd)).isoformat()


def _is_policy_active(policy: Dict[str, Any], on: Optional[datetime] = None) -> bool:
    """Cek masa berlaku policy (valid_from/valid_until)."""
    on = on or datetime.now(timezone.utc)
    vf = parse_dt(policy.get("valid_from"))
    vu = parse_dt(policy.get("valid_until"))
    if vf and on < vf:
        return False
    if vu and on > vu:
        return False
    return True


# ─── Supplier return policy ──────────────────────────────────────────────────

def normalize_supplier_policy(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Gabungkan default + policy tersimpan → objek policy lengkap & aman."""
    out = dict(DEFAULT_SUPPLIER_POLICY)
    out["custom_fields"] = {}
    if isinstance(raw, dict):
        for k in out:
            if k in raw and raw[k] is not None:
                out[k] = raw[k]
    # Normalisasi refund_modes ke subset kanonik (tetap izinkan kosong → none).
    modes = out.get("refund_modes") or []
    out["refund_modes"] = [m for m in modes if m in SUPPLIER_REFUND_MODES] or ["ap_credit"]
    try:
        out["window_days"] = int(out.get("window_days") or 0)
    except (ValueError, TypeError):
        out["window_days"] = 0
    try:
        out["restocking_fee_pct"] = float(out.get("restocking_fee_pct") or 0)
    except (ValueError, TypeError):
        out["restocking_fee_pct"] = 0.0
    out["returnable_to_supplier"] = bool(out.get("returnable_to_supplier", True))
    out["rma_required"] = bool(out.get("rma_required", False))
    if not isinstance(out.get("custom_fields"), dict):
        out["custom_fields"] = {}
    return out


def resolve_effective_origin(supplier: Dict[str, Any],
                             po: Optional[Dict[str, Any]] = None) -> str:
    """Asal barang efektif: override PO (`import_flag`) menang atas supplier.origin_type."""
    if po is not None:
        flag = po.get("import_flag")
        if flag is True:
            return "import"
        if flag is False:
            return "local"
    ot = (supplier or {}).get("origin_type") or "local"
    return ot if ot in ORIGIN_TYPES else "local"


def resolve_supplier_return_policy(supplier: Dict[str, Any],
                                   po: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Kembalikan policy retur supplier efektif + info asal barang + rekomendasi.

    Aturan cerdas (RETURNS_ANALYSIS §J): bila `import` & `returnable_to_supplier=false`
    → alur retur beli DILEWATI, barang defect diarahkan ke **regrade + jual lokal**.
    """
    policy = normalize_supplier_policy((supplier or {}).get("return_policy"))
    origin = resolve_effective_origin(supplier, po)
    returnable = bool(policy.get("returnable_to_supplier", True))
    # Impor yang tak returnable → rekomendasi regrade + jual lokal.
    recommend_regrade_local = (origin == "import" and not returnable)
    return {
        "supplier_id": (supplier or {}).get("id", ""),
        "supplier_name": (supplier or {}).get("name", ""),
        "origin_type": origin,
        "country": (supplier or {}).get("country", "") or "",
        "policy": policy,
        "returnable_to_supplier": returnable,
        "recommend_regrade_local": recommend_regrade_local,
        "resolved_at": now_iso(),
    }


# ─── Sales return policy resolution ──────────────────────────────────────────

async def _load_active_sales_policies(entity_id: str = "") -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"status": {"$ne": "inactive"}}
    if entity_id:
        # FASE E-4 (E4.3) — `"all"` ikut dianggap GLOBAL supaya kebijakan yang sudah
        # distempel migrasi tetap terbaca (dulu hanya ""/None yang dihitung global).
        q["$or"] = [{"entity_id": entity_id}, {"entity_id": ""}, {"entity_id": None},
                    {"entity_id": "all"}]
    rows = await db.sales_return_policies.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [r for r in rows if _is_policy_active(r)]


async def resolve_sales_return_policy(customer_id: str = "",
                                      categories: Optional[List[str]] = None,
                                      entity_id: str = "") -> Dict[str, Any]:
    """Pilih policy retur jual TERBAIK (prioritas: customer > category > global).

    Bila tak ada yang cocok → default sistem (window 30 hari, inspect wajib,
    window tidak dipaksa/hanya peringatan)."""
    policies = await _load_active_sales_policies(entity_id)
    categories = [c for c in (categories or []) if c]

    by_customer = [p for p in policies if p.get("scope") == "customer"
                   and p.get("scope_ref") == customer_id and customer_id]
    by_category = [p for p in policies if p.get("scope") == "category"
                   and p.get("scope_ref") in categories]
    by_global = [p for p in policies if p.get("scope") == "global"]

    for bucket in (by_customer, by_category, by_global):
        if bucket:
            # FASE E-4 (E4.3) — pada tingkat cakupan yang SAMA, kebijakan khusus badan
            # usaha MENANG atas kebijakan global; sesudah itu baru yang terbaru
            # (daftar sudah terurut created_at desc). Tanpa aturan ini kebijakan global
            # yang dibuat belakangan bisa mengalahkan kebijakan khusus badan usaha.
            own = [p for p in bucket
                   if entity_id and str(p.get("entity_id") or "") == entity_id]
            return {**(own[0] if own else bucket[0]), "is_default": False}
    return dict(DEFAULT_SALES_POLICY)


def snapshot_sales_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    """Snapshot ringkas policy untuk disematkan ke dokumen retur (auditable)."""
    keys = ("id", "name", "scope", "scope_ref", "window_days", "allowed_return_types",
            "allowed_outcomes", "restocking_fee_pct", "require_inspection",
            "enforce_window", "link_to_supplier_window", "condition_requirements",
            "custom_fields", "is_default")
    snap = {k: policy.get(k) for k in keys if k in policy}
    snap["snapshot_at"] = now_iso()
    return snap


# ─── Deadline (linked) + Eligibility retur jual ─────────────────────────────

def _order_reference_date(order: Dict[str, Any]) -> str:
    """Tanggal acuan jendela retur = saat barang dikirim ke customer.
    Prioritas: dispatched_at → shipped_at → confirmed_at → approved_at → created_at."""
    for k in ("dispatched_at", "shipped_at", "delivered_at",
              "confirmed_at", "approved_at", "created_at"):
        if order.get(k):
            return order[k]
    return ""


_PO_RECEIVED = ["receiving", "partial", "completed", "closed", "closed_short"]


def _roll_po_id(r: Dict[str, Any]) -> str:
    if r.get("po_id"):
        return r["po_id"]
    for acq in [r.get("acquired") or {}] + list(reversed(r.get("acquired_history") or [])):
        if acq.get("via") in ("inbound", "grn", "goods_receipt", "purchase"):
            pid = acq.get("po_id") or acq.get("ref_id") or ""
            if pid.startswith("po"):
                return pid
    return ""


async def physical_origin_po_ids(order_id: str) -> List[str]:
    """G3 D4-RET-POLICY-01 — asal FISIK: roll yang memenuhi SO → GR → PO; roll potongan
    ditelusuri lewat induknya. Asal disimpan di roll (bukan di tag), jadi re-tag tidak memutusnya."""
    rolls = await db.inventory_rolls.find(
        {"reserved_ref.type": "sales_order", "reserved_ref.id": order_id},
        {"_id": 0, "id": 1, "po_id": 1, "acquired": 1, "acquired_history": 1, "parent_roll_id": 1}).to_list(2000)
    out: List[str] = []
    for r in rolls:
        cur, hops = r, 0
        pid = _roll_po_id(cur)
        while not pid and cur.get("parent_roll_id") and hops < 10:
            cur = await db.inventory_rolls.find_one(
                {"id": cur["parent_roll_id"]},
                {"_id": 0, "po_id": 1, "acquired": 1, "acquired_history": 1, "parent_roll_id": 1}) or {}
            pid, hops = _roll_po_id(cur), hops + 1
        if pid and pid not in out:
            out.append(pid)
    return out


async def _linked_supplier_deadline(order: Dict[str, Any],
                                    window_fallback: int) -> Dict[str, Any]:
    """Deadline dari window supplier asal FISIK barang (roll → GR → PO); ambil yang TERKETAT.
    G3 D4-RET-POLICY-01: tidak lagi memakai "PO terbaru dengan produk sama" sebagai proxy.
    Bila asal tidak terlacak → source `untraceable` (keputusan bisnis: pakai kebijakan retur
    penjualan saja, retur ditandai untuk diperiksa Sales Admin)."""
    po_ids = await physical_origin_po_ids(order.get("id", ""))
    pos = await db.purchase_orders.find(
        {"id": {"$in": po_ids}, "status": {"$in": _PO_RECEIVED}}, {"_id": 0}).to_list(200) if po_ids else []
    best: Optional[Dict[str, Any]] = None
    for po in pos:
        supplier = await db.suppliers.find_one({"id": po.get("supplier_id")}, {"_id": 0}) if po.get("supplier_id") else None
        if not supplier:
            continue
        resolved = resolve_supplier_return_policy(supplier, po)
        win = int(resolved["policy"].get("window_days") or window_fallback)
        receipt = po.get("last_received_at") or po.get("updated_at") or po.get("created_at")
        cand = {
            "deadline": compute_deadline(receipt, win),
            "supplier_id": supplier.get("id", ""), "supplier_name": supplier.get("name", ""),
            "po_number": po.get("po_number", ""), "receipt_date": receipt, "window_days": win,
            "origin_type": resolved.get("origin_type"),
            "returnable_to_supplier": resolved.get("returnable_to_supplier"),
            "source": "supplier_linked", "origin_po_count": len(pos),
        }
        if best is None or (cand["deadline"] and (not best["deadline"] or cand["deadline"] < best["deadline"])):
            best = cand
    if best:
        return best
    return {"deadline": "", "supplier_id": "", "window_days": window_fallback, "source": "untraceable",
            "origin_untraceable": True}


RETURN_ASSUMPTION_DEFAULTS: Dict[str, Any] = {
    "customer_window_days": 21, "supplier_window_days": 21,
    "klr08_hangtag_cut": "pending",     # pending | reject | review — KLR-08 belum diputuskan owner
    "klr09_end_event": "pending",       # pending | request | goods_received — KLR-09 belum diputuskan owner
    "bill_first": True,                 # LN-091 disepakati: potong tagihan SO asal dulu (KLR-10: cakupan = SO asal)
    "cutloss_return_part": "pending",   # KLR-01: pending | defect_only | defect_plus_shorter | whole_roll
    "cutloss_value_basis": "pending",   # KLR-02: pending | line_price | net_after_discount
    "discount_mode": "pending",         # KLR-06/07: pending | approved_exception
    # LN-091-T02 — % harga daftar per grade (selisih lama vs baru = kerugian turun grade)
    "grade_price_factors": {"A": 100, "A1": 95, "A2": 90, "B": 70, "B1": 60, "C": 40, "BS": 10},
    "supplier_reminder_days": 3,        # LN-093 — pengingat ke PT pemasok sebelum masa retur supplier habis
}
_RECEIPT_VIA = ("inbound", "grn", "goods_receipt", "purchase", "receiving")


async def return_assumptions(entity_id: str = "") -> Dict[str, Any]:
    from services.config_service import get_effective_settings
    eff = await get_effective_settings(entity_id or None)
    return {**RETURN_ASSUMPTION_DEFAULTS, **(eff.get("returns") or {})}


async def customer_reference(order: Dict[str, Any]) -> Dict[str, Any]:
    """LN-083 — tanggal acuan customer = SJ penjualan (bukan tanggal SO). Disimpan beserta sumbernya."""
    shps = await db.shipments.find({"order_id": order.get("id"), "status": {"$nin": ["cancelled", "void", "draft"]}},
                                   {"_id": 0, "shipment_no": 1, "dispatched_at": 1, "created_at": 1}).to_list(200)
    rows = [{"number": x.get("shipment_no", ""), "date": x.get("dispatched_at") or x.get("created_at") or ""} for x in shps]
    rows = [r for r in rows if r["date"]]
    if rows:
        last = max(rows, key=lambda r: r["date"])
        return {"type": "shipment", "number": last["number"], "date": last["date"], "all": rows}
    date = _order_reference_date(order)
    return {"type": "order_field", "number": order.get("number", ""), "date": date, "all": []}


def _roll_receipt(r: Dict[str, Any]) -> Dict[str, str]:
    acq = r.get("acquired") or {}
    if acq.get("via") in _RECEIPT_VIA and acq.get("date"):
        return {"date": acq["date"], "source": f"penerimaan roll ({acq.get('via')})"}
    return {"date": r.get("received_at") or r.get("created_at") or "", "source": "roll tercatat di gudang"}


async def supplier_deadlines(rolls: List[Dict[str, Any]], fallback_days: int) -> List[Dict[str, Any]]:
    """LN-083-T02 — deadline klaim supplier per RECEIVING roll (bukan tanggal PO terakhir)."""
    groups: Dict[tuple, Dict[str, Any]] = {}
    po_cache: Dict[str, Any] = {}
    for r in rolls:
        rec = _roll_receipt(r)
        po_id = _roll_po_id(r)
        if not po_id:
            continue
        if po_id not in po_cache:
            po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0}) if po_id else None
            sup = await db.suppliers.find_one({"id": po.get("supplier_id")}, {"_id": 0}) if po and po.get("supplier_id") else None
            win = int(resolve_supplier_return_policy(sup, po)["policy"].get("window_days") or fallback_days) \
                if sup and (sup.get("return_policy") or {}).get("window_days") else fallback_days
            po_cache[po_id] = {"po": po or {}, "supplier": sup or {}, "window": win}
        meta = po_cache[po_id]
        key = (po_id, rec["date"][:10])
        g = groups.setdefault(key, {
            "po_id": po_id, "po_number": meta["po"].get("po_number", ""), "supplier_name": meta["supplier"].get("name", ""),
            "receipt_date": rec["date"], "source": rec["source"], "window_days": meta["window"],
            "deadline": compute_deadline(rec["date"], meta["window"]), "roll_ids": []})
        g["roll_ids"].append(r.get("id"))
    return sorted(groups.values(), key=lambda g: g["receipt_date"])


async def check_sales_return_eligibility(order: Dict[str, Any],
                                         return_type: str = "",
                                         on_date: Any = None,
                                         hangtag_missing: bool = False,
                                         cut_by_customer: bool = False) -> Dict[str, Any]:
    """Kelayakan retur jual (LN-083): batas customer dari SJ, independen dari batas supplier.

    Batas supplier (per receiving roll) hanya informasi untuk klaim lanjutan ke supplier dan TIDAK
    pernah menolak customer. KLR-08/KLR-09 yang belum diputuskan dilaporkan sebagai pending.
    """
    now = parse_dt(on_date) or datetime.now(timezone.utc)
    categories = list({it.get("category") for it in (order.get("items") or []) if it.get("category")})
    policy = await resolve_sales_return_policy(
        customer_id=order.get("customer_id", ""),
        categories=categories,
        entity_id=order.get("entity_id", ""),
    )
    assume = await return_assumptions(order.get("entity_id", ""))
    if policy.get("is_default"):
        policy = {**policy, "window_days": int(assume["customer_window_days"])}

    ref = await customer_reference(order)
    ref_date = ref["date"]
    window_days = int(policy.get("window_days") or 0)
    deadline = compute_deadline(ref_date, window_days)

    rolls = await db.inventory_rolls.find(
        {"reserved_ref.type": "sales_order", "reserved_ref.id": order.get("id", "")},
        {"_id": 0, "id": 1, "po_id": 1, "acquired": 1, "acquired_history": 1, "created_at": 1, "received_at": 1}).to_list(2000)
    sup_rows = await supplier_deadlines(rolls, int(assume["supplier_window_days"])) if rolls else []
    for g in sup_rows:
        d = parse_dt(g["deadline"])
        g["within_window"] = bool(d and now <= d)
    supplier_linked: Dict[str, Any] = {
        "source": "roll_receipts" if sup_rows else "untraceable", "receivings": sup_rows,
        "origin_untraceable": not sup_rows, "independent_of_customer": True,
        "any_expired": any(not g["within_window"] for g in sup_rows)}

    dl = parse_dt(deadline)
    within_window = True
    days_remaining: Optional[int] = None
    if dl:
        within_window = now <= dl
        days_remaining = (dl - now).days

    warnings: List[str] = []
    pending: List[Dict[str, str]] = []
    type_ok = True
    if return_type:
        allowed = policy.get("allowed_return_types") or []
        type_ok = return_type in allowed
        if not type_ok:
            warnings.append(
                f"Jenis retur '{return_type}' tidak diizinkan oleh kebijakan '{policy.get('name')}'.")
    if not ref_date:
        warnings.append("Tanggal SJ pengiriman tidak diketahui — deadline tak dapat dihitung.")
    if dl and not within_window:
        warnings.append(f"Di luar jendela retur customer ({window_days} hari dari SJ {ref.get('number') or ''}). "
                        f"Deadline {deadline[:10]}.")
    if dl and within_window and assume["klr09_end_event"] == "pending":
        pending.append({"code": "KLR-09", "message": "Pengajuan masih dalam batas. Apakah barang juga harus tiba di "
                        "gudang dalam 21 hari belum diputuskan owner — status akhir menunggu keputusan."})
    condition_block = False
    if hangtag_missing or cut_by_customer:
        mode = assume["klr08_hangtag_cut"]
        what = " & ".join(x for x, f in (("hangtag hilang", hangtag_missing), ("kain sudah dipotong", cut_by_customer)) if f)
        if mode == "pending":
            pending.append({"code": "KLR-08", "message": f"Kondisi {what}: aturan belum diputuskan owner — "
                            "tidak otomatis ditolak/diterima."})
        elif mode == "reject":
            condition_block = True
            warnings.append(f"Kondisi {what} ditolak (asumsi KLR-08 = tolak).")
        else:
            warnings.append(f"Kondisi {what} wajib diperiksa (asumsi KLR-08 = periksa).")
    needs_admin_review = bool(supplier_linked.get("origin_untraceable"))
    if needs_admin_review:
        warnings.append("Asal barang tidak terlacak sampai receiving — batas klaim supplier tidak dapat dihitung; "
                        "batas customer tetap berlaku.")
    elif supplier_linked["any_expired"]:
        warnings.append("Batas klaim ke supplier sudah lewat untuk sebagian receiving — retur customer TETAP dinilai "
                        "dengan batasnya sendiri.")

    enforce = bool(policy.get("enforce_window"))
    blocked = bool(enforce and dl is not None and not within_window) or condition_block
    eligible = type_ok and (within_window or not enforce) and not condition_block
    decision = "blocked" if blocked else ("outside_window" if dl and not within_window else
                                          ("pending_decision" if pending else ("eligible" if eligible else "review")))

    return {
        "order_id": order.get("id", ""),
        "order_number": order.get("number", ""),
        "customer_id": order.get("customer_id", ""),
        "eligible": eligible,
        "blocked": blocked,
        "decision": decision,
        "within_window": within_window,
        "reference_date": ref_date,
        "reference_source": {k: ref[k] for k in ("type", "number", "date")},
        "window_days": window_days,
        "deadline": deadline,
        "days_remaining": days_remaining,
        "require_inspection": bool(policy.get("require_inspection", True)),
        "restocking_fee_pct": float(policy.get("restocking_fee_pct") or 0),
        "allowed_return_types": policy.get("allowed_return_types") or [],
        "allowed_outcomes": policy.get("allowed_outcomes") or [],
        "supplier_linked": supplier_linked,
        "origin_untraceable": needs_admin_review,
        "needs_admin_review": needs_admin_review,
        "pending_decisions": pending,
        "assumptions": {**assume, "is_assumption": True},
        "warnings": warnings,
        "policy": {**snapshot_sales_policy(policy), "assumptions": assume},
        "evaluated_at": now_iso(),
    }
