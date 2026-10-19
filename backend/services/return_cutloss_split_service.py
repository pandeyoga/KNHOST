"""CUT-01..05 — pemecahan fisik roll cutloss setelah QC: potongan baik / BS / dibuang.

Owner 2026-10-19D: yang memilih BS/Dibuang = peran di `returns.cutloss_treatment_roles` (bawaan MD);
BS dicatat per satuan dasar (kg/yard), bukan per roll, nilai = HPP proporsional (CUT-03); dipecah setelah QC
selesai (CUT-04); potongan baik dikirim balik dengan Surat Jalan baru yang merujuk SJ & SO asal (CUT-05).
"""
from typing import Any, Dict, List

from core_utils import new_id, now_iso
from db import db
from services import gl_service
from services.roll_service import PHYSICAL_ROLL_STATUSES, insert_child_roll, rebuild_balance, to_base_qty

ROLES_KEY = "returns.cutloss_treatment_roles"
TREATMENTS = {"bs": "Masuk stok BS", "dispose": "Dibuang"}
SPLIT_STATUSES = ("inspected",)
EPS = 0.001


async def assert_can_choose(actor: Dict[str, Any], entity_id: str) -> None:
    from services import config_resolver
    roles = await config_resolver.value_of(ROLES_KEY, {"entity_id": entity_id} if entity_id else None) or []
    if actor.get("role") in ("admin", "manager") or actor.get("role") in roles:
        return
    raise PermissionError("Peran Anda tidak diatur untuk memilih potongan cacat masuk BS atau dibuang")


def _entry(ret: Dict[str, Any], ctl_id: str) -> Dict[str, Any]:
    e = next((c for c in ret.get("cutloss") or [] if c.get("id") == ctl_id), None)
    if not e:
        raise LookupError("Catatan cutloss tidak ditemukan")
    return e


async def _to_roll_unit(prod: Dict[str, Any], roll: Dict[str, Any], yards: float) -> float:
    unit = (roll.get("unit") or prod.get("base_unit") or "yard").lower()
    if unit == "yard":
        return round(yards, 4)
    return round(await to_base_qty(prod, yards, "yard"), 4)


async def _plan(ret: Dict[str, Any], e: Dict[str, Any]) -> Dict[str, Any]:
    if ret.get("status") not in SPLIT_STATUSES:
        raise ValueError("Roll dipecah setelah QC selesai (status retur: inspeksi selesai).")
    if not e.get("roll_id"):
        raise ValueError("Cutloss tanpa roll di gudang (customer menyimpan kain) tidak memecah roll.")
    if e.get("treatment") not in TREATMENTS:
        raise ValueError("Pilih perlakuan potongan cacat dulu: Masuk stok BS atau Dibuang.")
    roll = await db.inventory_rolls.find_one({"id": e["roll_id"]}, {"_id": 0})
    if not roll or roll.get("status") not in PHYSICAL_ROLL_STATUSES:
        raise ValueError("Roll tidak ada di gudang — tidak bisa dipecah.")
    prod = await db.products.find_one({"id": roll["product_id"]}, {"_id": 0}) or {}
    length = float(roll.get("length_remaining") or 0)
    if e.get("defect_from") is not None and e.get("defect_to") is not None:
        f, t = await _to_roll_unit(prod, roll, e["defect_from"]), await _to_roll_unit(prod, roll, e["defect_to"])
    else:
        t, f = length, max(0.0, length - await _to_roll_unit(prod, roll, e["defect_yard"]))
    if not (0 <= f < t <= length + EPS):
        raise ValueError(f"Posisi cacat di luar panjang roll ({length:g} {roll.get('unit', '')}).")
    t = min(t, length)
    cost = float(roll.get("unit_cost") or roll.get("base_unit_cost") or 0)
    pieces = []
    for kind, a, b in (("good", 0.0, f), ("defect", f, t), ("good", t, length)):
        q = round(b - a, 4)
        if q > EPS:
            treat = e["treatment"] if kind == "defect" else "return_customer"
            pieces.append({"kind": kind, "treatment": treat, "from": round(a, 2), "to": round(b, 2), "qty": q,
                           "unit": roll.get("unit", ""), "grade": "BS" if kind == "defect" else (roll.get("grade") or ""),
                           "value": round(q * cost, 2),
                           "label": "Baik — kirim balik ke customer" if kind == "good" else TREATMENTS[e["treatment"]]})
    summary = " · ".join(f"{p['qty']:g} {p['unit']} {'baik' if p['kind'] == 'good' else TREATMENTS[p['treatment']].lower()}" for p in pieces)
    return {"roll": roll, "pieces": pieces, "summary": summary, "unit_cost": cost}


async def preview(ret: Dict[str, Any], ctl_id: str) -> Dict[str, Any]:
    p = await _plan(ret, _entry(ret, ctl_id))
    return {"roll_no": p["roll"].get("roll_no", ""), "length": p["roll"].get("length_remaining"),
            "pieces": p["pieces"], "summary": p["summary"]}


def _child(parent: Dict[str, Any], piece: Dict[str, Any], ret: Dict[str, Any], status: str) -> Dict[str, Any]:
    c = {**parent, "id": new_id("roll"), "length": piece["qty"], "length_initial": piece["qty"],
         "length_remaining": piece["qty"], "grade": piece["grade"], "status": status, "updated_at": now_iso(),
         "created_at": now_iso(), "cutloss_piece": {"return_id": ret["id"], "kind": piece["kind"],
                                                    "treatment": piece["treatment"], "from": piece["from"], "to": piece["to"]}}
    for k in ("return_history", "acquired_history", "return_restore"):
        c.pop(k, None)
    return c


async def _post(lines_keys: List[tuple], amount: float, sid: str, entity: str, label: str) -> Dict[str, Any]:
    (dr, cr) = lines_keys
    return await gl_service._insert_entry(
        lines=[{"account_key": dr, "debit": amount, "credit": 0.0, "description": label},
               {"account_key": cr, "debit": 0.0, "credit": amount, "description": label}],
        description=label, date=now_iso(), source_type="return_cutloss", source_id=sid, entity_id=entity,
        created_by="system", source_label=label)


async def execute(ret: Dict[str, Any], ctl_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    e = _entry(ret, ctl_id)
    if e.get("split", {}).get("status") == "done":
        raise ValueError("Roll cutloss ini sudah dipecah.")
    await assert_can_choose(actor, ret.get("entity_id", ""))
    plan = await _plan(ret, e)
    parent, pieces = plan["roll"], plan["pieces"]
    claim = await db.inventory_rolls.find_one_and_update(
        {"id": parent["id"], "length_remaining": parent.get("length_remaining"), "cutloss_split_lock": {"$exists": False}},
        {"$set": {"cutloss_split_lock": ctl_id}})
    if not claim:
        raise ValueError("Roll sedang diubah proses lain — muat ulang.")
    entity, num, out = parent.get("owner_entity_id") or ret.get("entity_id", ""), ret.get("number", ""), []
    basis = {"w": float(parent.get("weight_kg") or 0), "len": float(parent.get("length_remaining") or 0)}
    for i, pc in enumerate(pieces):
        status = "available" if pc["treatment"] == "bs" else "hold"
        if i == 0:
            await db.inventory_rolls.update_one({"id": parent["id"]}, {"$set": {
                "length_remaining": pc["qty"], "length": pc["qty"], "grade": pc["grade"], "status": status,
                "cutloss_piece": _child(parent, pc, ret, status)["cutloss_piece"], "updated_at": now_iso()},
                "$unset": {"cutloss_split_lock": ""}})
            doc = {**parent, "length_remaining": pc["qty"], "status": status, "grade": pc["grade"]}
        else:
            doc = await insert_child_roll(_child(parent, pc, ret, status), parent, basis)
        pc.update(roll_id=doc["id"], roll_no=doc.get("roll_no", ""), status=status)
        lbl = f"Cutloss {num} · {doc.get('roll_no', '')}"
        if pc["treatment"] == "dispose" and pc["value"] > 0:
            je = await _post(("retur.cutloss_dibuang", "persediaan.persediaan"), pc["value"], f"{ctl_id}:{doc['id']}:dispose",
                             entity, f"Potongan cacat dibuang · {lbl}")
            pc["journal_entry_number"] = je.get("number", "")
        if pc["treatment"] == "dispose":
            await db.inventory_rolls.update_one({"id": doc["id"]}, {"$set": {
                "status": "damaged", "length_remaining": 0, "disposed_qty": pc["qty"], "disposed_at": now_iso(),
                "writeoff_amount": pc["value"]}})
            pc["status"] = "damaged"
            await db.inventory_movements.insert_one({
                "id": new_id("mov"), "product_id": parent["product_id"], "warehouse_id": parent.get("warehouse_id", ""),
                "owner_entity_id": entity, "type": "return_disposal", "movement_type": "return_disposal", "direction": "out",
                "quantity": pc["qty"], "unit": pc["unit"], "roll_id": doc["id"], "qty_rolls": 1, "ref_type": "sales_return",
                "ref_id": ret["id"], "source_document": ret["id"], "timestamp": now_iso(),
                "notes": f"Potongan cacat cutloss dibuang (retur {num})"})
        if pc["treatment"] == "bs" and pc["value"] > 0 and \
                await gl_service.account_for("retur.cutloss_bs", entity) != await gl_service.account_for("persediaan.persediaan", entity):
            je = await _post(("retur.cutloss_bs", "persediaan.persediaan"), pc["value"], f"{ctl_id}:{doc['id']}:bs",
                             entity, f"Reklas potongan BS · {lbl}")
            pc["journal_entry_number"] = je.get("number", "")
        out.append(pc)
    await db.inventory_rolls.update_one({"id": parent["id"]}, {"$unset": {"cutloss_split_lock": ""}})
    await rebuild_balance(parent["product_id"], parent.get("warehouse_id", ""), entity)
    split = {"status": "done", "pieces": out, "summary": plan["summary"], "by": actor.get("name", ""), "at": now_iso()}
    await db.sales_returns.update_one({"id": ret["id"], "cutloss.id": ctl_id},
                                      {"$set": {"cutloss.$.split": split, "updated_at": now_iso()}})
    return split


async def _orig_shipment(ret: Dict[str, Any], roll_id: str) -> Dict[str, Any]:
    root = await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0, "root_roll_id": 1, "parent_roll_id": 1})
    ids = [x for x in {roll_id, (root or {}).get("root_roll_id"), (root or {}).get("parent_roll_id")} if x]
    return await db.shipments.find_one({"order_id": ret.get("order_id"), "rolls.roll_id": {"$in": ids}},
                                       {"_id": 0, "id": 1, "shipment_no": 1}) or {}


async def create_return_sj(ret: Dict[str, Any], ctl_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """CUT-05 — SJ baru untuk potongan baik, merujuk SJ & SO asal. Roll keluar stok saat SJ dibuat."""
    e = _entry(ret, ctl_id)
    split = e.get("split") or {}
    if split.get("status") != "done":
        raise ValueError("Pecah roll dulu sebelum membuat Surat Jalan potongan baik.")
    if split.get("shipment_no"):
        raise ValueError(f"Surat Jalan sudah dibuat: {split['shipment_no']}")
    good = [p for p in split.get("pieces", []) if p["kind"] == "good"]
    if not good:
        raise ValueError("Tidak ada potongan baik untuk dikirim balik.")
    from services.shipment_service import _next_shipment_no
    entity = ret.get("entity_id", "")
    orig = await _orig_shipment(ret, e["roll_id"])
    no = await _next_shipment_no(entity)
    rolls, total_val = [], 0.0
    for p in good:
        r = await db.inventory_rolls.find_one_and_update({"id": p["roll_id"], "status": "hold"}, {"$set": {
            "status": "delivered", "delivered_at": now_iso(), "updated_at": now_iso()}}, projection={"_id": 0})
        if not r:
            raise ValueError(f"Roll {p.get('roll_no')} tidak lagi menunggu kirim balik.")
        rolls.append({"roll_id": r["id"], "roll_no": r.get("roll_no", ""), "qty": p["qty"], "unit": p["unit"]})
        total_val += p["value"]
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": r["product_id"], "warehouse_id": r.get("warehouse_id", ""),
            "owner_entity_id": r.get("owner_entity_id", ""), "type": "cutloss_return_customer",
            "movement_type": "cutloss_return_customer", "direction": "out", "quantity": p["qty"], "unit": p["unit"],
            "roll_id": r["id"], "qty_rolls": 1, "ref_type": "sales_return", "ref_id": ret["id"], "source_document": no,
            "timestamp": now_iso(), "notes": f"Potongan baik cutloss dikirim balik (retur {ret.get('number', '')})"})
        await rebuild_balance(r["product_id"], r.get("warehouse_id", ""), r.get("owner_entity_id", ""))
    if total_val > 0:
        await _post(("persediaan.hpp", "persediaan.persediaan"), round(total_val, 2), f"{ctl_id}:sj", entity,
                    f"Potongan baik cutloss dikirim balik · {no}")
    doc = {"id": new_id("shp"), "shipment_no": no, "kind": "cutloss_return", "entity_id": entity, "order_id": "",
           "ref_order_id": ret.get("order_id", ""), "ref_order_number": ret.get("order_number", ""),
           "ref_shipment_id": orig.get("id", ""), "ref_shipment_no": orig.get("shipment_no", ""),
           "return_id": ret["id"], "return_number": ret.get("number", ""), "customer_id": ret.get("customer_id", ""),
           "customer_name": ret.get("customer_name", ""), "rolls": rolls, "quantity": round(sum(x["qty"] for x in rolls), 2),
           "status": "dispatched", "created_by": actor.get("name", ""), "created_at": now_iso(), "logistics_id": ""}
    await db.shipments.insert_one(dict(doc))
    await db.sales_returns.update_one({"id": ret["id"], "cutloss.id": ctl_id}, {"$set": {
        "cutloss.$.split.shipment_no": no, "cutloss.$.split.shipment_id": doc["id"], "updated_at": now_iso()}})
    doc.pop("_id", None)
    return doc
