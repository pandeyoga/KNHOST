"""L08 LN-082 — identitas roll retur: roll utuh kembali dengan ID/nomor/EPC yang sama,
potongan menjadi child berurutan dari induk, dan larangan kirim ulang ke pelanggan asal."""
from typing import Any, Dict, List, Optional, Tuple

from pymongo.errors import DuplicateKeyError

from db import db
from services.tolerances import QTY_EPS

# Field yang dipulihkan bila penyelesaian retur dibalik (reverse_settlement).
RESTORE_KEYS = ("status", "warehouse_id", "owner_entity_id", "length", "length_remaining", "grade",
                "condition", "defects", "inspection", "unit_cost", "base_unit_cost", "landed_cost_total",
                "reserved_ref", "earmarked_for", "committed_to", "origin_type", "origin_ref", "qc_status",
                "journey", "acquired", "delivered_at")
BLOCK_KEY = "returns.block_resend_to_origin_customer"


async def block_policy_on(entity_id: Optional[str]) -> bool:
    from services import config_resolver
    return bool(await config_resolver.value_of(BLOCK_KEY, {"entity_id": entity_id} if entity_id and entity_id != "all" else None))


def blocked_for(roll: Dict[str, Any], customer_id: str) -> bool:
    return bool(customer_id) and customer_id in (roll.get("returned_from_customer_ids") or [])


async def assert_not_origin_customer(roll: Dict[str, Any], customer_id: str, entity_id: str) -> None:
    if blocked_for(roll, customer_id) and await block_policy_on(entity_id):
        raise ValueError(
            f"Roll {roll.get('roll_no') or roll.get('id')} adalah barang retur (atau turunannya) dari pelanggan "
            "ini dan tidak boleh dikirim ulang ke pelanggan yang sama selama kebijakan "
            "'Larang kirim ulang roll retur ke pelanggan asal' aktif.")


def _split_actuals(roll_ids: List[str], claims: Dict[str, float], actuals: Dict[str, float],
                   qty: float) -> Dict[str, float]:
    """Qty aktual per roll: hasil ukur QC bila ada, selain itu klaim per roll diskalakan ke qty efektif."""
    if actuals:
        return {rid: round(float(actuals.get(rid, claims.get(rid, 0)) or 0), 2) for rid in roll_ids}
    total = sum(float(claims.get(rid, 0) or 0) for rid in roll_ids)
    if total <= 0:
        return {rid: round(qty / len(roll_ids), 2) for rid in roll_ids}
    f = min(1.0, qty / total)
    return {rid: round(float(claims.get(rid, 0) or 0) * f, 2) for rid in roll_ids}


def _history_entry(ret: Dict[str, Any], orig: Dict[str, Any], claimed: float, actual: float,
                   grade_after: str, ship_no: str, now: str) -> Dict[str, Any]:
    return {"return_id": ret["id"], "return_number": ret.get("number", ""),
            "order_id": ret.get("order_id", ""), "order_number": ret.get("order_number", ""),
            "shipment_no": ship_no, "customer_id": ret.get("customer_id", ""),
            "customer_name": ret.get("customer_name", ""),
            "source_roll_id": orig["id"], "source_roll_no": orig.get("roll_no", ""),
            "qty_shipped_bruto": round(float(orig.get("length_initial") or orig.get("length_remaining") or 0), 2),
            "qty_claimed": round(claimed, 2), "qty_actual": round(actual, 2), "unit": orig.get("unit", ""),
            "grade_before": orig.get("grade") or "", "grade_after": grade_after, "at": now}


async def _shipment_no(order_id: str, roll_id: str) -> str:
    s = await db.shipments.find_one({"order_id": order_id, "rolls.roll_id": roll_id},
                                    {"_id": 0, "shipment_no": 1})
    return (s or {}).get("shipment_no") or ""


async def _insert_return_child(child: Dict[str, Any], parent_no: str) -> Dict[str, Any]:
    from services.roll_service import child_roll_no, next_roll_no
    doc = dict(child)
    for _ in range(20):
        doc["roll_no"] = await child_roll_no(parent_no)
        try:
            await db.inventory_rolls.insert_one(dict(doc))
            return doc
        except DuplicateKeyError as exc:
            if "roll_no" not in str(exc):
                raise
    doc["roll_no"] = await next_roll_no()
    await db.inventory_rolls.insert_one(dict(doc))
    return doc


async def restock_identity(ret: Dict[str, Any], item: Dict[str, Any], template: Dict[str, Any],
                           qty: float, now: str) -> List[Tuple[Dict[str, Any], float]]:
    """Masukkan roll terkirim yang kembali ke karantina TANPA membuat identitas baru.

    Roll utuh (status `delivered`, qty aktual ≈ panjang terkirim) diaktifkan lagi dengan id,
    nomor & tag yang sama; selain itu potongan retur dibuat sebagai child `<nomor induk>-N`.
    Return: daftar (dokumen roll, qty) untuk pencatatan mutasi."""
    roll_ids = [r for r in (item.get("roll_ids") or []) if r]
    claims = {k: float(v or 0) for k, v in (item.get("roll_qtys") or {}).items()}
    insp = item.get("inspection") or {}
    actuals = _split_actuals(roll_ids, claims, insp.get("roll_actuals") or {}, qty)
    grade_after = template.get("grade") or "A"
    out: List[Tuple[Dict[str, Any], float]] = []
    for rid in roll_ids:
        actual = actuals.get(rid, 0)
        if actual <= 0:
            continue
        orig = await db.inventory_rolls.find_one({"id": rid}, {"_id": 0})
        if not orig:
            continue
        ship_no = await _shipment_no(ret.get("order_id", ""), rid)
        # 23 Okt — grade & cacat PER ROLL dari SPK QC retur (dulu satu grade baris untuk semua roll).
        rr = (insp.get("roll_results") or {}).get(rid) or {}
        grade_roll = rr.get("grade") or grade_after
        hist = _history_entry(ret, orig, claims.get(rid, actual), actual, grade_roll, ship_no, now)
        customers = sorted(set((orig.get("returned_from_customer_ids") or []) + [ret.get("customer_id", "")]) - {""})
        live = {k: template[k] for k in ("status", "qc_status", "warehouse_id", "owner_entity_id", "condition",
                                         "defects", "inspection", "unit_cost", "base_unit_cost", "origin_type",
                                         "origin_ref", "return_id", "journey") if k in template}
        if rr:
            live.update({"defects": rr.get("defects") or [], "inspection": {**(template.get("inspection") or {}), **rr}})
        live.update({"grade": grade_roll, "length": actual, "length_remaining": actual,
                     "landed_cost_total": round(max(float(template.get("unit_cost") or 0)
                                                    - float(template.get("base_unit_cost") or 0), 0) * actual, 2),
                     "reserved_ref": None, "earmarked_for": None, "committed_to": None,
                     "returned_from_customer_ids": customers, "updated_at": now})
        # Utuh = pelanggan mengembalikan seluruh roll (klaim ≈ panjang terkirim); qty aktual boleh beda.
        from services.return_journey_service import physical_warehouse
        live["warehouse_id"] = physical_warehouse(ret, rid) or live.get("warehouse_id")   # LN-081 lokasi scan
        whole = (orig.get("status") == "delivered"
                 and claims.get(rid, actual) >= float(orig.get("length_remaining") or 0) - QTY_EPS)
        if whole:
            snap = {k: orig.get(k) for k in RESTORE_KEYS}
            upd = await db.inventory_rolls.find_one_and_update(
                {"id": rid, "status": "delivered"},
                {"$set": {**live, "returned_identity": True, "return_restore": snap,
                          "acquired": {"via": "return", "ref_id": ret["id"], "date": now}},
                 "$push": {"return_history": hist, "acquired_history": orig.get("acquired") or {}}},
                projection={"_id": 0}, return_document=True)
            if upd:
                out.append((upd, actual))
                continue
        child = {**template, **live, "id": _new_roll_id(), "unit": orig.get("unit") or template.get("unit"),
                 "length_initial": actual, "parent_roll_id": rid,
                 "root_roll_id": orig.get("root_roll_id") or rid, "rfid_tag_id": None,
                 "return_history": list(orig.get("return_history") or []) + [hist]}
        out.append((await _insert_return_child(child, orig.get("roll_no") or ""), actual))
    return out


def _new_roll_id() -> str:
    from core_utils import new_id
    return new_id("roll")


async def restore_identity_roll(roll: Dict[str, Any], now: str) -> None:
    """Balik aktivasi roll utuh saat penyelesaian retur di-reverse (roll kembali 'di pelanggan')."""
    snap = dict(roll.get("return_restore") or {})
    hist = list(roll.get("return_history") or [])
    if hist and hist[-1].get("return_id") == roll.get("return_id"):
        hist = hist[:-1]
    customers = sorted({h.get("customer_id") for h in hist if h.get("customer_id")})
    await db.inventory_rolls.update_one(
        {"id": roll["id"], "returned_identity": True},
        {"$set": {**snap, "return_history": hist, "returned_from_customer_ids": customers, "updated_at": now},
         "$unset": {"return_restore": "", "returned_identity": "", "return_id": ""}})
