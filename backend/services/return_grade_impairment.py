"""LN-091-T02 — kerugian turun grade barang retur.

Nilai = selisih harga daftar grade lama vs grade baru per satuan (faktor % per grade bisa diatur
di Pengaturan → returns.grade_price_factors), dibatasi nilai buku roll. Dicatat terpisah dari
kredit pelanggan/AR; invoice & nota kredit lama tidak disentuh.
"""
from typing import Any, Dict, Optional

from core_utils import new_id, now_iso
from db import db
from services import gl_service
from services import roll_cost_history as _cost_history
from services.return_policy_service import return_assumptions

DEFAULT_FACTORS: Dict[str, float] = {"A": 100, "A1": 95, "A2": 90, "B": 70, "B1": 60, "C": 40, "BS": 10}
COLL = "return_grade_impairments"


async def grade_factors(entity_id: str = "") -> Dict[str, float]:
    a = await return_assumptions(entity_id)
    return {**DEFAULT_FACTORS, **{k: float(v) for k, v in (a.get("grade_price_factors") or {}).items()}}


def compute(list_price: float, book_unit: float, f_old: float, f_new: float, qty: float) -> Dict[str, Any]:
    drop = max(float(f_old) - float(f_new), 0.0) / 100.0
    unit_diff = round(float(list_price or 0) * drop, 2)
    unit_loss = round(min(unit_diff, max(float(book_unit or 0), 0.0)), 2)
    return {"unit_price_diff": unit_diff, "unit_loss": unit_loss,
            "amount": round(unit_loss * float(qty or 0), 2), "capped_to_book": unit_loss < unit_diff}


async def record(ret: Dict[str, Any], roll: Dict[str, Any], old_grade: str, new_grade: str,
                 actor: str) -> Optional[Dict[str, Any]]:
    """Dipanggil saat release karantina dengan regrade. `roll` = dokumen SEBELUM nilai diubah."""
    prior = await db[COLL].find_one({"return_id": ret["id"], "roll_id": roll["id"]}, {"_id": 0})
    if prior:
        return prior
    owner = roll.get("owner_entity_id") or ret.get("entity_id", "")
    factors = await grade_factors(owner)
    f_old, f_new = factors.get(old_grade, 100.0), factors.get(new_grade, 100.0)
    if f_new >= f_old:
        return None
    prod = await db.products.find_one({"id": roll.get("product_id")}, {"_id": 0, "price": 1}) or {}
    qty = float(roll.get("length_remaining", roll.get("length", 0)) or 0)
    book = float(roll.get("unit_cost") or roll.get("base_unit_cost") or 0)
    calc = compute(float(prod.get("price") or 0), book, f_old, f_new, qty)
    if calc["amount"] <= 0.01:
        return None
    sid = f"{ret['id']}:{roll['id']}"
    label = f"{roll.get('roll_no') or roll['id']} (retur {ret.get('number', '')}) {old_grade}→{new_grade}"
    je = await gl_service.post_return_grade_impairment(source_id=sid, entity_id=owner,
                                                        amount=calc["amount"], label=label)
    new_unit = round(book - calc["unit_loss"], 2)
    base = float(roll.get("base_unit_cost") or book)
    upd = await db.inventory_rolls.update_one({"id": roll["id"]}, {"$set": {
        "unit_cost": new_unit, "base_unit_cost": round(max(base - calc["unit_loss"], 0.0), 2),
        "grade_impairment_amount": calc["amount"], "updated_at": now_iso()}})
    if upd.modified_count:
        await _cost_history.record(roll, new_unit, "return_grade_impairment", actor=actor,
                                   ref_type="sales_return", ref_id=ret["id"], ref_number=ret.get("number", ""))
    doc = {"id": new_id("rgi"), "return_id": ret["id"], "return_number": ret.get("number", ""),
           "roll_id": roll["id"], "roll_no": roll.get("roll_no", ""), "product_id": roll.get("product_id", ""),
           "entity_id": owner, "grade_before": old_grade, "grade_after": new_grade, "qty": round(qty, 2),
           "unit": roll.get("unit", ""), "list_price": float(prod.get("price") or 0),
           "factor_before": f_old, "factor_after": f_new, "book_unit_before": round(book, 2),
           "book_unit_after": new_unit, **calc, "je_id": (je or {}).get("id", ""),
           "je_number": (je or {}).get("number", ""), "created_by": actor, "created_at": now_iso()}
    await db[COLL].insert_one(dict(doc))
    await db.sales_returns.update_one({"id": ret["id"]}, {"$inc": {"grade_impairment_total": calc["amount"]},
                                                         "$set": {"updated_at": now_iso()}})
    return doc


async def list_for_return(return_id: str) -> Dict[str, Any]:
    items = await db[COLL].find({"return_id": return_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return {"items": items, "total": round(sum(i["amount"] for i in items), 2)}
