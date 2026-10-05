"""P10 — stock opname: scope hitung per bin, adjustment per baris (CAS) + jurnal selisih.

Kebijakan valuasi DEFAULT (menunggu konfirmasi pemilik buku, dicatat di IMPLEMENTATION P10):
  - Kekurangan  : nilai = Σ(panjang dipotong × unit_cost roll) → Dr 5-9500 Beban Kerugian Persediaan / Cr 1-1300.
  - Kelebihan   : roll baru dinilai WAC segmen (produk×gudang×pemilik → produk×pemilik → biaya standar
                  produk) → Dr 1-1300 / Cr 4-9000 Pendapatan Lain-lain (selisih lebih opname).
  - Biaya 0     : wajib `zero_cost_reason` eksplisit saat approve (else 409).
"""
import math
from typing import Any, Dict, List, Tuple

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso
from services.roll_service import PHYSICAL_ROLL_STATUSES, create_inbound_roll, rebuild_balance

# Urutan potong kekurangan (risiko terendah dulu). Semua bucket fisik ikut — sama dengan scope expected.
SHORTAGE_ORDER = {"available": 0, "hold": 1, "quarantine": 1, "blocked": 1, "damaged": 1, "wip": 1,
                  "reserved": 2, "committed": 2, "picked": 3, "packed": 3}
assert set(SHORTAGE_ORDER) == set(PHYSICAL_ROLL_STATUSES)
EPS = 0.001


def count_key(item: Dict[str, Any]) -> Tuple[str, str, str]:
    return (item.get("product_id") or "", item.get("owner_entity_id") or "", item.get("bin_id") or "")


def _scope_q(product_id: str, warehouse_id: str, owner: str, bin_id: str) -> Dict[str, Any]:
    q: Dict[str, Any] = {"product_id": product_id, "warehouse_id": warehouse_id, "owner_entity_id": owner,
                         "status": {"$in": PHYSICAL_ROLL_STATUSES}, "length_remaining": {"$gt": 0}}
    if bin_id:
        q["bin_id"] = bin_id
    return q


async def scope_qty(product_id: str, warehouse_id: str, owner: str, bin_id: str = "") -> float:
    """WM-07 — expected = roll fisik pada scope hitung (bin bila diisi), satu definisi dengan on_hand."""
    rows = await db.inventory_rolls.aggregate([
        {"$match": _scope_q(product_id, warehouse_id, owner, bin_id)},
        {"$group": {"_id": None, "q": {"$sum": "$length_remaining"}}}]).to_list(1)
    return round(float(rows[0]["q"]) if rows else 0.0, 2)


def valid_qty(v: Any) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Jumlah aktual tidak valid")
    if not math.isfinite(f) or f < 0:
        raise HTTPException(status_code=400, detail="Jumlah aktual wajib angka ≥ 0 (bukan negatif/NaN/∞)")
    return round(f, 4)


async def surplus_unit_cost(product_id: str, warehouse_id: str, owner: str) -> Tuple[float, str]:
    for basis, q in (("wac_gudang", {"warehouse_id": warehouse_id}), ("wac_pemilik", {})):
        rows = await db.inventory_rolls.aggregate([
            {"$match": {"product_id": product_id, "owner_entity_id": owner, "length_remaining": {"$gt": 0},
                        "status": {"$in": PHYSICAL_ROLL_STATUSES}, **q}},
            {"$project": {"l": "$length_remaining", "v": {"$multiply": ["$length_remaining",
                                                                       {"$ifNull": ["$unit_cost", {"$ifNull": ["$base_unit_cost", 0]}]}]}}},
            {"$group": {"_id": None, "l": {"$sum": "$l"}, "v": {"$sum": "$v"}}}]).to_list(1)
        if rows and rows[0]["l"] > EPS and rows[0]["v"] > EPS:
            return round(rows[0]["v"] / rows[0]["l"], 4), basis
    prod = await db.products.find_one({"id": product_id}, {"_id": 0}) or {}
    for k in ("standard_cost", "cost_price", "purchase_price", "base_price_cost"):
        if float(prod.get(k) or 0) > 0:
            return float(prod[k]), f"produk.{k}"
    return 0.0, "tidak_ada"


async def _shortage(item: Dict[str, Any], warehouse_id: str, need: float, ref: str) -> Dict[str, Any]:
    """WM-08 — potong roll dengan CAS (length & status saat dibaca); balapan → baca ulang, bukan menimpa."""
    q = _scope_q(item["product_id"], warehouse_id, item["owner_entity_id"], item.get("bin_id") or "")
    applied, value, touched, rolls_out = 0.0, 0.0, set(), []
    for _attempt in range(3):
        rolls = await db.inventory_rolls.find(q, {"_id": 0}).to_list(10000)
        rolls.sort(key=lambda r: (SHORTAGE_ORDER.get(r.get("status"), 9), r.get("created_at", ""),
                                  -float(r.get("length_remaining", 0))))
        for r in rolls:
            if need - applied <= EPS:
                break
            rlen = float(r["length_remaining"])
            take = round(min(rlen, need - applied), 2)
            new_len = round(rlen - take, 2)
            upd = {"length_remaining": 0.0, "status": "consumed"} if new_len <= EPS else {"length_remaining": new_len}
            res = await db.inventory_rolls.update_one(
                {"id": r["id"], "length_remaining": r["length_remaining"], "status": r["status"]},
                {"$set": {**upd, "updated_at": now_iso()}})
            if res.modified_count != 1:
                continue  # roll berubah bersamaan (mis. reservasi) — lewati, dicoba di putaran berikut
            cost = float(r.get("unit_cost") or r.get("base_unit_cost") or 0)
            applied = round(applied + take, 2)
            value += take * cost
            if r.get("status") in ("reserved", "committed", "picked", "packed") and r.get("reserved_ref"):
                touched.add(str((r.get("reserved_ref") or {}).get("id") if isinstance(r.get("reserved_ref"), dict) else r["reserved_ref"]))
            rolls_out.append({"roll_id": r["id"], "status": r["status"], "qty": take, "unit_cost": cost})
            await db.inventory_movements.insert_one({
                "id": new_id("mov"), "product_id": item["product_id"], "warehouse_id": warehouse_id,
                "owner_entity_id": item["owner_entity_id"], "movement_type": "cycle_count_adjustment",
                "quantity": -take, "unit": r.get("unit", "meter"), "lot": r.get("lot", ""), "roll_id": r["id"],
                "qty_rolls": 1, "source_document": ref, "unit_cost": cost, "timestamp": now_iso()})
        if need - applied <= EPS:
            break
    return {"applied": applied, "value": round(value, 2), "touched_orders": sorted(touched), "rolls": rolls_out}


async def apply_line(session: Dict[str, Any], item: Dict[str, Any], diff: float, actor: str,
                     zero_cost_reason: str = "") -> Dict[str, Any]:
    """Terapkan selisih SATU baris hitung → roll + movement + jurnal. Hasil: requested/applied/unresolved."""
    from services import gl_service as gl
    wh, owner = session["warehouse_id"], item["owner_entity_id"]
    ref = f"{session['id']}:{item['id']}"
    label = f"Opname {session.get('name', session['id'])} · {item.get('sku') or item['product_id']}"
    adj: Dict[str, Any] = {"requested": round(diff, 2), "at": now_iso(), "by": actor}
    if diff > 0:
        cost, basis = await surplus_unit_cost(item["product_id"], wh, owner)
        roll = await create_inbound_roll(item["product_id"], wh, owner, round(diff, 2), bin_id=item.get("bin_id") or None,
                                         acquired_via="cycle_count_adjustment", ref_id=session["id"],
                                         created_by=actor, unit_cost=cost)
        value = round(diff * cost, 2)
        adj.update({"applied": round(diff, 2), "unit_cost": cost, "cost_basis": basis, "value": value,
                    "roll_ids": [roll.get("id")], "zero_cost_reason": zero_cost_reason if cost <= 0 else ""})
    else:
        res = await _shortage(item, wh, -diff, ref)
        adj.update({"applied": -res["applied"], "value": -res["value"], "rolls": res["rolls"],
                    "touched_orders": res["touched_orders"]})
        if res["touched_orders"]:
            try:
                from services.notification_service import notify_cycle_count_hit_reservation
                await notify_cycle_count_hit_reservation(product_id=item["product_id"], warehouse_id=wh, entity_id=owner,
                                                         order_ids=res["touched_orders"], shortage_qty=-diff,
                                                         session_number=session.get("name", ""))
            except Exception:  # noqa: BLE001 — notifikasi bukan bagian kontrak stok
                pass
    await rebuild_balance(item["product_id"], wh, owner)
    adj["unresolved"] = round(adj["requested"] - adj["applied"], 2)
    je = await gl.post_cycle_count_variance(source_id=ref, entity_id=owner, amount_signed=adj["value"], label=label)
    adj["journal_id"] = (je or {}).get("id")
    adj["status"] = "applied" if abs(adj["unresolved"]) <= EPS else "exception"
    return adj


async def feasibility(session: Dict[str, Any], lines: List[Tuple[Dict[str, Any], float]], zero_cost_reason: str) -> None:
    """Validasi SEBELUM mutasi: shortage harus tertutup stok eligible scope; surplus biaya 0 butuh alasan."""
    problems: List[str] = []
    for item, diff in lines:
        if diff < 0:
            have = await scope_qty(item["product_id"], session["warehouse_id"], item["owner_entity_id"], item.get("bin_id") or "")
            if have + EPS < -diff:
                problems.append(f"{item.get('sku')}: kurang {-diff:g} tetapi stok eligible {have:g}")
        elif diff > 0 and not zero_cost_reason:
            cost, _ = await surplus_unit_cost(item["product_id"], session["warehouse_id"], item["owner_entity_id"])
            if cost <= 0:
                problems.append(f"{item.get('sku')}: kelebihan tanpa biaya acuan — isi alasan biaya nol (zero_cost_reason)")
    if problems:
        raise HTTPException(status_code=409, detail="Opname tidak dapat diterapkan: " + "; ".join(problems[:5]))
