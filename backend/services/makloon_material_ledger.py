"""L04 LN-043 — buku bahan makloon per MKO: forecast · dicadangkan · dikirim/di mitra · terpakai · kembali · susut.

Hanya-baca. Fisik gudang tidak berkurang sebelum issue (cadangan = soft-reservation). Hasil penerimaan aktual = SSOT;
estimasi resep/yield hanya pembanding. Rekonsiliasi per langkah: dikirim = di mitra + kembali + susut + terpakai.
"""
from typing import Any, Dict, List

from db import db
from services import material_reservation_service as mres
from services import stock_bucket_service as sb

EPS = 0.01


def _r(v: Any) -> float:
    return round(float(v or 0), 3)


async def _stock(product_id: str, entity_id: str) -> Dict[str, float]:
    rows = await db.inventory_balances.find({"product_id": product_id, "owner_entity_id": entity_id},
                                            {"_id": 0, "on_hand_qty": 1, "available_qty": 1, "subcon_qty": 1}).to_list(None)
    on_hand = _r(sum(float(r.get("on_hand_qty") or 0) for r in rows))
    available = _r(sum(float(r.get("available_qty") or 0) for r in rows))
    reserved_all = await mres.reserved_by_others(product_id, entity_id)
    return {"on_hand": on_hand, "available_physical": available, "reserved_all_orders": _r(reserved_all),
            "free_for_new_commitment": _r(max(available - reserved_all, 0.0)),
            "at_partners_all_orders": _r(sum(float(r.get("subcon_qty") or 0) for r in rows))}


async def _step_row(s: Dict[str, Any]) -> Dict[str, Any]:
    status = s.get("status")
    moves = str(s.get("material_flow") or "moves") != "service_only"
    issued = _r(s.get("input_qty")) if moves and status in ("issued", "received", "returned") else 0.0
    at_partner = _r(await sb.subcon_qty_by_ref(s["issue_ref"])) if status == "issued" and s.get("issue_ref") else 0.0
    returned = _r(sum(float(r.get("qty") or 0) for r in s.get("material_returns") or []))
    lost = _r(sum(float(x.get("qty") or 0) for x in s.get("material_losses") or [] if x.get("status") == "posted"))
    loss_pending = _r(sum(float(x.get("qty") or 0) for x in s.get("material_losses") or []
                          if x.get("status") == "pending_approval"))
    consumed = _r(((s.get("receive_progress") or {}).get("consumed") or {}).get("consumed_qty")
                  or (issued - returned - lost if status == "received" else 0))
    gap = _r(issued - at_partner - returned - lost - consumed)
    exp_out, act_out = _r(s.get("expected_output_qty")), _r(s.get("actual_output_qty"))
    return {"seq": s.get("seq"), "stage": s.get("stage_label") or s.get("process_type"), "status": status,
            "makloon_name": s.get("makloon_name", ""), "material_moves": moves,
            "input_unit": s.get("input_unit", ""), "output_unit": s.get("output_unit", ""),
            "forecast_input": _r(s.get("input_qty")), "issued": issued, "at_partner": at_partner,
            "returned": returned, "lost": lost, "loss_pending_approval": loss_pending, "consumed": consumed,
            "awaiting_return": bool(s.get("awaiting_return")),
            "forecast_output": exp_out, "actual_output": act_out if status == "received" else None,
            "output_variance": _r(act_out - exp_out) if status == "received" else None,
            "reconciled": abs(gap) <= EPS, "unexplained": gap}


async def material_ledger(order: Dict[str, Any]) -> Dict[str, Any]:
    pid, ent = order.get("material_product_id") or "", order.get("entity_id") or ""
    res = await db.material_reservations.find({"ref_id": order["id"]}, {"_id": 0, "history": 0}).to_list(20)
    reserved_active = _r(sum(float(r.get("qty") or 0) for r in res if r.get("status") == "active"))
    steps = [await _step_row(s) for s in order.get("steps", [])]
    first = next((x for x in steps if x["material_moves"]), None)
    out = {
        "mko_id": order["id"], "mko_number": order.get("mko_number"), "status": order.get("status"),
        "mode": order.get("mode"), "material_product_id": pid, "material_name": order.get("material_name", ""),
        "unit": order.get("material_unit", ""),
        "forecast_need": _r(order.get("material_qty")),
        "reservation": {"required": _r(sum(float(r.get("required_qty") or 0) for r in res)),
                        "active": reserved_active,
                        "consumed_by_issue": _r(sum(float(r.get("consumed_qty") or 0) for r in res)),
                        "shortage": _r(sum(float(r.get("shortage_qty") or 0) for r in res if r.get("status") == "active")),
                        "statuses": sorted({r.get("status") for r in res})},
        "material": {k: (first or {}).get(k, 0.0) for k in ("issued", "at_partner", "returned", "lost", "consumed")},
        "steps": steps, "reconciled": all(x["reconciled"] for x in steps),
        "stock_now": await _stock(pid, ent) if pid else None,
        "final_output": {"forecast": _r((order.get("forecast") or {}).get("expected_finished_qty")),
                         "actual": _r((order.get("costing") or {}).get("steps", [{}])[-1].get("actual_output_qty"))
                         if order.get("status") in ("completed", "partial") else None,
                         "unit": order.get("final_output_unit", "")},
    }
    out["explain"] = _explain(out)
    return out


def _explain(x: Dict[str, Any]) -> List[str]:
    u, m, rv = x["unit"], x["material"], x["reservation"]
    lines = [f"Kebutuhan bahan (estimasi resep): {x['forecast_need']:g} {u}."]
    if rv["required"]:
        lines.append(f"Dicadangkan {rv['active']:g} {u} (belum keluar gudang; fisik tidak berkurang)"
                     + (f", kurang {rv['shortage']:g} {u}" if rv["shortage"] > EPS else "") + ".")
    if m["issued"]:
        lines.append(f"Dikirim ke mitra {m['issued']:g} {u} — fisik gudang berkurang saat issue; cadangan terpakai "
                     f"{rv['consumed_by_issue']:g} {u}.")
    if m["at_partner"]:
        lines.append(f"Masih di mitra {m['at_partner']:g} {u} (milik kita, tercatat WIP/subcon).")
    if m["returned"] or m["lost"]:
        lines.append(f"Kembali ke gudang {m['returned']:g} {u}; susut/hilang disetujui {m['lost']:g} {u}.")
    if m["consumed"]:
        lines.append(f"Terpakai menjadi hasil {m['consumed']:g} {u}; hasil dihitung dari penerimaan aktual, bukan estimasi.")
    lines.append("Saldo seimbang." if x["reconciled"] else "Ada selisih bahan yang belum dijelaskan — periksa langkah bertanda.")
    return lines
