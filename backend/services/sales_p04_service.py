"""P04 — Keep/Pending, aturan grade pelanggan, kandidat roll berkelayakan, ringkasan stok Sales.

Keputusan pemilik 2026-10-11:
  DEC-01 Keep = SO belum diverifikasi Admin Sales; batas umur dapat dikonfigurasi (`sales.keep_max_age_days`,
         0 = tanpa batas) dan hanya memberi tanda "lewat batas" — tidak membatalkan / menahan stok.
  DEC-01 Pending = sisa backorder aktif. Roll berkomitmen SO yang masih di transfer BUKAN Pending, tampil
         sebagai "dalam perjalanan".
  DEC-04 BS tampil ke Sales sebagai pilihan terpisah; aturan grade per pelanggan diisi lewat form (belum ada data).
  DEC-13 tagihan mengikuti qty roll aktual yang dikirim (mesin pembulatan roll W2-REQ-09 sudah demikian).
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db import db
from core_utils import new_id, now_iso
from domain_registry import grade_rank

EPS = 0.01
KEEP_STATUSES = ["draft", "reserved", "waiting_approval", "pending_approval", "approved", "waiting_stock", "confirmed"]
OPEN_SO = KEEP_STATUSES + ["partially_picked", "picked", "partially_shipped"]
TRANSIT_TRF = ["dispatched", "in_transit", "partially_received"]
STATUS_LABEL = {"reserved": "Sudah dikunci", "quarantine": "Karantina QC", "blocked": "Ditahan", "hold": "Ditahan",
                "damaged": "Rusak", "in_transit_transfer": "Dalam perjalanan transfer", "picked": "Sudah diambil",
                "packed": "Sudah dikemas", "wip": "Sedang diproses", "in_transit_sales": "Dikirim ke pelanggan"}


def _age_days(iso: str) -> int:
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - dt).days)
    except Exception:  # noqa: BLE001
        return 0


async def keep_limit_days(entity_id: str) -> int:
    from services import config_resolver
    try:
        return int(await config_resolver.value_of("sales.keep_max_age_days", {"entity_id": entity_id}) or 0)
    except Exception:  # noqa: BLE001
        return 0


def _active_backorders(o: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [b for b in o.get("backorders") or []
            if b.get("status") != "fulfilled" and float(b.get("backorder_qty") or 0) > EPS]


def _so_row(o: Dict[str, Any]) -> Dict[str, Any]:
    return {"order_id": o["id"], "number": o.get("number"), "customer_name": o.get("customer_name", ""),
            "status": o.get("status"), "entity_id": o.get("entity_id"), "created_at": o.get("created_at"),
            "age_days": _age_days(o.get("created_at")), "grand_total": round(float(o.get("grand_total") or 0), 2),
            "sales_name": o.get("sales_name") or o.get("created_by") or ""}


async def _transit_by_order(order_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Roll berkomitmen SO yang masih di jalan (transfer pemenuhan SO) — per SO × produk × satuan."""
    out: Dict[str, Dict[tuple, Dict[str, Any]]] = {}
    trfs = await db.warehouse_transfers.find({"sales_order_id": {"$in": order_ids}, "status": {"$in": TRANSIT_TRF}},
                                             {"_id": 0}).to_list(500)
    for t in trfs:
        ids = [x["roll_id"] for it in t.get("items") or [] for x in it.get("rolls") or [] if x.get("roll_id")]
        moving = {r["id"] for r in await db.inventory_rolls.find(
            {"id": {"$in": ids}, "status": "in_transit_transfer"}, {"_id": 0, "id": 1}).to_list(len(ids) + 1)}
        for it in t.get("items") or []:
            rolls = [x for x in it.get("rolls") or [] if x.get("roll_id") in moving]
            if not rolls:
                continue
            key = (it.get("product_id"), it.get("unit") or "")
            row = out.setdefault(t["sales_order_id"], {}).setdefault(key, {
                "product_id": it.get("product_id"), "product_name": it.get("product_name", ""), "sku": it.get("sku", ""),
                "unit": it.get("unit") or "", "qty": 0.0, "rolls": 0, "transfers": []})
            row["qty"] = round(row["qty"] + sum(float(x.get("length") or 0) for x in rolls), 2)
            row["rolls"] += len(rolls)
            row["transfers"].append({"id": t["id"], "code": t.get("code"), "status": t.get("status")})
    return {k: list(v.values()) for k, v in out.items()}


async def _mko_refs(pr_id: str) -> List[Dict[str, Any]]:
    """P05 — jalur produksi: Order Makloon dari PR + status bahan (dicadangkan/kurang/terkirim)."""
    out = []
    async for m in db.makloon_orders.find({"pr_id": pr_id}, {"_id": 0, "id": 1, "mko_number": 1, "status": 1,
                                                              "expected_delivery_date": 1, "material_name": 1,
                                                              "material_unit": 1, "forecast": 1}):
        res = await db.material_reservations.find(
            {"ref_id": m["id"]}, {"_id": 0, "qty": 1, "shortage_qty": 1, "status": 1, "consumed_qty": 1}).to_list(10)
        out.append({"id": m["id"], "number": m.get("mko_number"), "status": m.get("status"),
                    "eta": m.get("expected_delivery_date") or "", "material_name": m.get("material_name", ""),
                    "material_unit": m.get("material_unit", ""),
                    "expected_output": (m.get("forecast") or {}).get("expected_finished_qty"),
                    "material_reserved": round(sum(float(r.get("qty") or 0) for r in res if r.get("status") == "active"), 2),
                    "material_shortage": round(sum(float(r.get("shortage_qty") or 0) for r in res if r.get("status") == "active"), 2),
                    "material_issued": round(sum(float(r.get("consumed_qty") or r.get("qty") or 0)
                                                 for r in res if r.get("status") == "consumed"), 2)})
    return out


async def _supply_refs(o: Dict[str, Any], product_id: str) -> List[Dict[str, Any]]:
    """Dokumen pemenuhan NYATA dari keputusan Admin Sales (tanpa nomor fiktif)."""
    from services import fulfillment_decision_service as fds
    refs: List[Dict[str, Any]] = []
    seen: set = set()
    for d in reversed(fds.decision_history(o)):
        parts = [p for p in d.get("parts") or [] if p.get("product_id") == product_id]
        if not parts and product_id in (d.get("products") or []):
            parts = [{"mode": d.get("mode"), "qty": 0, "ref_type": d.get("ref_type"), "ref_id": d.get("ref_id"),
                      "ref_number": d.get("ref_number"), "promise_date": d.get("promise_date")}]
        for p in parts:
            if p.get("mode") == "stock" or (p.get("ref_id") and p.get("ref_id") in seen):
                continue
            seen.add(p.get("ref_id"))
            ref = {"mode": p.get("mode"), "qty": round(float(p.get("qty") or 0), 2), "ref_type": p.get("ref_type") or "",
                   "ref_id": p.get("ref_id") or "", "ref_number": p.get("ref_number") or "",
                   "eta": p.get("promise_date") or "", "status": "", "note": ""}
            if ref["ref_type"] in ("purchase_requisition", "pr") and ref["ref_id"]:
                pr = await db.purchase_requisitions.find_one({"id": ref["ref_id"]}, {"_id": 0, "status": 1, "po_id": 1,
                                                                                     "po_number": 1, "items": 1}) or {}
                ref["status"] = pr.get("status", "")
                line = next((i for i in pr.get("items") or [] if i.get("product_id") == product_id), {})
                ref["qty"] = ref["qty"] or round(float(line.get("quantity") or 0), 2)
                if line.get("fulfillment_mode") == "makloon":
                    ref["mode"] = "makloon"
                if pr.get("po_id"):
                    po = await db.purchase_orders.find_one({"id": pr["po_id"]}, {"_id": 0, "po_number": 1, "status": 1,
                                                                               "expected_date": 1}) or {}
                    ref.update(po_id=pr["po_id"], po_number=po.get("po_number") or pr.get("po_number") or "",
                               po_status=po.get("status", ""), eta=po.get("expected_date") or ref["eta"])
                elif ref["mode"] == "makloon":
                    ref["note"] = "PR makloon belum menjadi Order Makloon"
                else:
                    ref["note"] = "PR belum menjadi PO"
                ref["makloon_orders"] = await _mko_refs(ref["ref_id"])
                if ref["makloon_orders"]:
                    ref["note"] = "PR direalisasi ke Order Makloon"
                    ref["eta"] = ref["eta"] or next((m["eta"] for m in ref["makloon_orders"] if m["eta"]), "")
            if ref["mode"] == "wait":
                ref["note"] = "Tunggu barang datang — perkiraan, tidak dijamin"
            refs.append(ref)
    return refs


async def keep_pending(scope: Dict[str, Any], entity_id: str) -> Dict[str, Any]:
    q = {**scope, "status": {"$in": OPEN_SO}}
    orders = await db.sales_orders.find(q, {"_id": 0}).sort("created_at", 1).to_list(3000)
    limit = await keep_limit_days(entity_id)
    keep, pend_map, pend_ids = [], {}, set()
    transit = await _transit_by_order([o["id"] for o in orders])
    for o in orders:
        bos = _active_backorders(o)
        if bos:
            pend_ids.add(o["id"])
        items = {i.get("product_id"): i for i in o.get("items") or []}
        for b in bos:
            it = items.get(b.get("product_id")) or {}
            unit = b.get("unit") or it.get("base_unit") or it.get("unit") or ""
            key = (b.get("product_id"), unit)
            p = pend_map.setdefault(key, {"product_id": b.get("product_id"),
                                          "product_name": b.get("product_name") or it.get("product_name", ""),
                                          "sku": b.get("sku") or it.get("sku", ""), "unit": unit, "short_qty": 0.0,
                                          "orders": []})
            qty = round(float(b.get("backorder_qty") or 0), 2)
            p["short_qty"] = round(p["short_qty"] + qty, 2)
            p["orders"].append({**_so_row(o), "short_qty": qty, "supply": await _supply_refs(o, b.get("product_id"))})
        verified = (o.get("verification") or {}).get("status") == "verified"
        if not verified and o.get("status") in KEEP_STATUSES:
            row = _so_row(o)
            row.update(also_pending=bool(bos), overdue=bool(limit and row["age_days"] > limit),
                       items_count=len(o.get("items") or []))
            keep.append(row)
    pending = sorted(pend_map.values(), key=lambda p: -len(p["orders"]))
    for p in pending:
        p["so_count"] = len({r["order_id"] for r in p["orders"]})
        p["supply_unknown_eta"] = any(not s.get("eta") for r in p["orders"] for s in r["supply"])
    in_transit = [{**_so_row(o), "lines": transit[o["id"]]} for o in orders if transit.get(o["id"])]
    keep_ids = {k["order_id"] for k in keep}
    return {"keep": keep, "pending": pending, "in_transit": in_transit,
            "keep_limit_days": limit,
            "counts": {"keep": len(keep), "keep_overdue": sum(1 for k in keep if k["overdue"]),
                       "pending_orders": len(pend_ids), "pending_products": len(pending),
                       "in_transit_orders": len(in_transit), "both": len(keep_ids & pend_ids),
                       "unique_orders": len(keep_ids | pend_ids)}}


# ── Aturan grade pelanggan (DEC-04: form, belum ada data) ─────────────────────

def _clean_grades(vals: List[str]) -> List[str]:
    from services.grade_service import normalize_or_raise
    out: List[str] = []
    for v in vals or []:
        g = normalize_or_raise(v)
        if g not in out:
            out.append(g)
    return out


async def get_rule(customer_id: str) -> Optional[Dict[str, Any]]:
    return await db.customer_grade_rules.find_one({"customer_id": customer_id}, {"_id": 0})


def _min_of(rule: Optional[Dict[str, Any]]) -> str:
    """L01 LN-012 — minimum grade pelanggan. Aturan lama (`allowed_grades`) dibaca sebagai
    minimum = grade terburuk yang dulu diterima (tidak pernah memperketat diam-diam)."""
    if not rule:
        return ""
    if rule.get("min_grade"):
        return rule["min_grade"]
    old = [g for g in (rule.get("allowed_grades") or []) if g != "BS"]
    return max(old, key=_rank) if old else ""


async def save_rule(customer: Dict[str, Any], body: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    from services.grade_service import normalize_or_raise
    raw_min = (body.get("min_grade") or "").strip()
    min_grade = normalize_or_raise(raw_min, "Minimum grade") if raw_min else ""
    if min_grade == "BS":
        raise ValueError("Minimum grade tidak boleh BS — BS dijual sebagai pilihan terpisah (centang 'menerima BS').")
    preferred = _clean_grades(body.get("preferred_grades") or [])
    accept_bs = bool(body.get("accept_bs"))
    bad = [g for g in preferred if g == "BS" or (min_grade and _rank(g) > _rank(min_grade))]
    if bad:
        raise ValueError(f"Grade prioritas {', '.join(bad)} di bawah minimum {min_grade or '-'} pelanggan.")
    cur = await get_rule(customer["id"]) or {}
    keys = ("min_grade", "preferred_grades", "accept_bs")
    rec = {"min_grade": min_grade, "preferred_grades": preferred, "accept_bs": accept_bs,
           "note": (body.get("note") or "").strip()[:300], "updated_by": actor.get("name", ""), "updated_at": now_iso()}
    hist = {"at": rec["updated_at"], "by": rec["updated_by"],
            "before": ({**{k: cur.get(k) for k in keys}, "min_grade": _min_of(cur)} if cur else None),
            "after": {k: rec[k] for k in keys}}
    await db.customer_grade_rules.update_one(
        {"customer_id": customer["id"]},
        {"$set": rec, "$unset": {"allowed_grades": ""},
         "$setOnInsert": {"id": new_id("cgr"), "customer_id": customer["id"],
                          "customer_name": customer.get("name", ""), "created_at": rec["updated_at"]},
         "$push": {"history": {"$each": [hist], "$slice": -30}}}, upsert=True)
    return await get_rule(customer["id"])


def grade_block_reason(rule: Optional[Dict[str, Any]], grade: str, line_is_bs: bool = False) -> str:
    g = grade or ""
    if g == "BS" and not line_is_bs:
        if not (rule or {}).get("accept_bs"):
            return "BS dijual sebagai pilihan terpisah — baris ini bukan BS"
        return ""
    if g != "BS" and line_is_bs:
        return "Baris ini pilihan BS — hanya roll BS"
    mn = _min_of(rule)
    if mn and g != "BS":
        if grade_rank(g) is None:
            return f"Grade roll belum ditetapkan — pelanggan minimum {mn}"
        if _rank(g) > _rank(mn):
            return f"Grade {g} di bawah minimum pelanggan ({mn}); grade lebih tinggi boleh"
    return ""


def _rank(g: str) -> int:
    return grade_rank(g) or 99


def recommend(rule: Optional[Dict[str, Any]], stock_by_grade: Dict[str, float]) -> Dict[str, Any]:
    if not rule:
        return {"grade": "", "reason": "Belum ada aturan grade untuk pelanggan ini — Admin Sales memilih sendiri."}
    mn = _min_of(rule)
    ok = [g for g in stock_by_grade if g != "BS" and (not mn or _rank(g) <= _rank(mn))]
    order = [g for g in (rule.get("preferred_grades") or []) if g in ok] + sorted(
        [g for g in ok if g not in (rule.get("preferred_grades") or [])], key=_rank)
    for g in order:
        if stock_by_grade.get(g, 0) > EPS:
            src = "prioritas pelanggan" if g in (rule.get("preferred_grades") or []) else "grade terbaik yang memenuhi minimum"
            return {"grade": g, "reason": f"Grade {g} — {src}; stok layak {stock_by_grade[g]:g}. Admin Sales tetap meninjau."}
    return {"grade": "", "reason": f"Tidak ada stok layak sesuai minimum grade {mn or '-'} pelanggan."}


async def candidates(order: Dict[str, Any], product_id: str, limit: int = 120) -> Dict[str, Any]:
    from services.roll_service import PHYSICAL_ROLL_STATUSES
    item = next((i for i in order.get("items") or [] if i.get("product_id") == product_id), {}) or {}
    line_is_bs = (item.get("quality_class") == "bs") or (item.get("grade") == "BS")
    rule = await get_rule(order.get("customer_id") or "")
    statuses = list(PHYSICAL_ROLL_STATUSES) + ["in_transit_transfer"]
    rolls = await db.inventory_rolls.find(
        {"product_id": product_id, "status": {"$in": statuses}, "length_remaining": {"$gt": 0}},
        {"_id": 0, "id": 1, "roll_no": 1, "lot": 1, "grade": 1, "status": 1, "length_remaining": 1, "unit": 1,
         "warehouse_id": 1, "owner_entity_id": 1, "reserved_ref": 1, "created_at": 1}).sort(
        [("status", 1), ("created_at", 1)]).to_list(limit)
    whs = {w["id"]: w.get("name", w["id"]) async for w in db.warehouses.find({}, {"_id": 0, "id": 1, "name": 1})}
    ents = {e["id"]: e.get("short_name") or e["id"] async for e in db.business_entities.find({}, {"_id": 0, "id": 1, "short_name": 1})}
    picking = {t.get("roll_id") async for t in db.wms_tasks.find(
        {"roll_id": {"$in": [r["id"] for r in rolls]}, "status": {"$in": ["picking", "packing", "staging"]}},
        {"_id": 0, "roll_id": 1})}
    ref_ids = list({(r.get("reserved_ref") or {}).get("id") for r in rolls if r.get("reserved_ref")} - {None, order["id"]})
    so_nums = {s["id"]: s.get("number") async for s in db.sales_orders.find({"id": {"$in": ref_ids}}, {"_id": 0, "id": 1, "number": 1})}
    out, by_grade = [], {}
    for r in rolls:
        ref = r.get("reserved_ref") or {}
        mine = ref.get("id") == order["id"]
        reasons = []
        if r.get("owner_entity_id") != order.get("entity_id"):
            reasons.append(f"Milik {ents.get(r.get('owner_entity_id'), 'PT lain')} — lewat Keputusan Pemenuhan (antar-PT)")
        if r.get("status") == "reserved" and not mine:
            reasons.append(f"Sudah dikunci untuk {so_nums.get(ref.get('id')) or ref.get('type') or 'dokumen lain'}")
        elif r.get("status") not in ("available", "reserved"):
            reasons.append(STATUS_LABEL.get(r.get("status"), r.get("status")))
        if r["id"] in picking:
            reasons.append("Sedang dalam pengambilan gudang")
        gr = grade_block_reason(rule, r.get("grade") or "", line_is_bs)
        if gr:
            reasons.append(gr)
        eligible = not reasons
        if eligible and not mine:
            by_grade[r.get("grade") or ""] = round(by_grade.get(r.get("grade") or "", 0.0) + float(r["length_remaining"]), 2)
        out.append({**{k: r.get(k) for k in ("id", "roll_no", "lot", "grade", "status", "unit", "owner_entity_id")},
                    "length_remaining": round(float(r["length_remaining"]), 2),
                    "warehouse_name": whs.get(r.get("warehouse_id"), ""), "owner_entity_name": ents.get(r.get("owner_entity_id"), ""),
                    "current": mine, "eligible": eligible or mine, "reasons": reasons})
    return {"order_id": order["id"], "product_id": product_id, "unit": item.get("base_unit") or item.get("unit") or "",
            "line_is_bs": line_is_bs, "rule": rule, "recommendation": recommend(rule, by_grade), "items": out}


async def assert_rolls_allowed(order: Dict[str, Any], product_id: str, roll_ids: List[str]) -> None:
    """Revalidasi server untuk Ganti Roll: grade vs aturan pelanggan & BS terpisah."""
    if not roll_ids:
        return
    item = next((i for i in order.get("items") or [] if i.get("product_id") == product_id), {}) or {}
    line_is_bs = (item.get("quality_class") == "bs") or (item.get("grade") == "BS")
    rule = await get_rule(order.get("customer_id") or "")
    async for r in db.inventory_rolls.find({"id": {"$in": roll_ids}}, {"_id": 0, "roll_no": 1, "grade": 1}):
        why = grade_block_reason(rule, r.get("grade") or "", line_is_bs)
        if why:
            raise ValueError(f"Roll {r.get('roll_no')}: {why}.")


async def sales_stock_summary(product_id: str, entity_id: str) -> Dict[str, Any]:
    """Ringkasan stok untuk Sales: Reguler (non-BS) dan BS terpisah; tanpa LOT/grade rinci/pemilik."""
    from services.stock_bucket_service import _incoming_supply
    from services.atp_policy import compute_atp, pending_backorder_qty, sum_incoming_in_horizon
    prod = await db.products.find_one({"id": product_id}, {"_id": 0, "id": 1, "name": 1, "base_unit": 1}) or {}
    rows: Dict[str, Dict[str, float]] = {}
    pipe = [{"$match": {"product_id": product_id, "length_remaining": {"$gt": 0}}},
            {"$group": {"_id": {"bs": {"$eq": ["$grade", "BS"]}, "own": {"$eq": ["$owner_entity_id", entity_id]},
                                "st": "$status"}, "q": {"$sum": "$length_remaining"}}}]
    async for g in db.inventory_rolls.aggregate(pipe):
        cls = "bs" if g["_id"]["bs"] else "regular"
        r = rows.setdefault(cls, {"physical": 0.0, "reserved": 0.0, "free": 0.0, "blocked": 0.0, "in_transit": 0.0,
                                  "group_free": 0.0})
        st, q = g["_id"]["st"], float(g["q"] or 0)
        if not g["_id"]["own"]:
            if st == "available":
                r["group_free"] += q
            continue
        if st in ("available", "reserved", "hold", "quarantine", "blocked", "picked", "packed", "damaged"):
            r["physical"] += q
        if st == "available":
            r["free"] += q
        elif st in ("reserved", "picked", "packed", "hold"):
            r["reserved"] += q
        elif st in ("quarantine", "blocked", "damaged"):
            r["blocked"] += q
        elif st.startswith("in_transit"):
            r["in_transit"] += q
    incoming = await _incoming_supply(product_id, entity_id) if entity_id else []
    inc_h = sum_incoming_in_horizon(incoming)
    demand = await pending_backorder_qty(product_id, entity_id)
    out = []
    for cls, label in (("regular", "Reguler (non-BS)"), ("bs", "BS")):
        r = {k: round(v, 2) for k, v in (rows.get(cls) or {}).items()}
        if not r and cls == "bs":
            continue
        r = {"physical": 0.0, "reserved": 0.0, "free": 0.0, "blocked": 0.0, "in_transit": 0.0, "group_free": 0.0, **r}
        row = {"class": cls, "label": label, **r}
        if cls == "regular":
            row.update(incoming=round(sum(float(i.get("qty") or 0) for i in incoming), 2), incoming_in_horizon=inc_h,
                       pending_demand=demand, atp=compute_atp(r["free"], inc_h, demand))
        out.append(row)
    return {"product_id": product_id, "product_name": prod.get("name", ""), "unit": prod.get("base_unit", ""),
            "entity_id": entity_id, "rows": out,
            "note": "Stok PT lain di grup bukan milik Anda — penggunaannya diputuskan Admin Sales."}
