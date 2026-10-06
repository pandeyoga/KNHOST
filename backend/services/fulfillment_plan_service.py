"""2026-10 — RENCANA PEMENUHAN per baris (keputusan pemilik): Admin Sales membagi
kekurangan tiap baris ke: stok sendiri · transfer dari PT lain (bisa >1 PT) · PO supplier
(lewat PR) · tunggu barang datang. Boleh penuh atau sebagian; sisa tetap backorder.
Mesin yang dipakai = mesin lama (`fulfillment_decision_service`, `backorder_service`).
"""
from typing import Any, Dict, List

from db import db
from core_utils import now_iso
from services import fulfillment_decision_service as fds
from services.fulfillment_decision_service import FulfillmentError

EPS = 0.01
NON_STOCK = ("interco", "reorder", "wait")


async def _entity_names() -> Dict[str, str]:
    rows = await db.business_entities.find({}, {"_id": 0, "id": 1, "short_name": 1, "legal_name": 1}).to_list(200)
    return {e["id"]: e.get("short_name") or e.get("legal_name") or e["id"] for e in rows}


async def _own_by_warehouse(product_id: str, entity_id: str) -> List[Dict[str, Any]]:
    names = {w["id"]: w.get("name", w["id"]) async for w in db.warehouses.find({}, {"_id": 0, "id": 1, "name": 1})}
    out = []
    async for b in db.inventory_balances.find(
            {"product_id": product_id, "owner_entity_id": entity_id, "available_qty": {"$gt": 0}}, {"_id": 0}):
        out.append({"warehouse_id": b["warehouse_id"], "warehouse_name": names.get(b["warehouse_id"], b["warehouse_id"]),
                    "available_qty": round(float(b.get("available_qty") or 0), 2)})
    return out


def _planned(order: Dict[str, Any]) -> Dict[str, float]:
    """Kumulatif qty yang SUDAH direncanakan (transfer/PR/tunggu) per produk — untuk panduan."""
    out: Dict[str, float] = {}
    for d in fds.decision_history(order):
        for p in d.get("parts") or []:
            if p.get("mode") in NON_STOCK:
                out[p["product_id"]] = round(out.get(p["product_id"], 0.0) + float(p.get("qty") or 0), 2)
    return out


async def plan_options(order: Dict[str, Any]) -> Dict[str, Any]:
    from services.internal_request_service import availability
    kurang = await fds.shortages(order)
    buyer = order.get("entity_id") or ""
    names = await _entity_names()
    items = {it.get("product_id"): it for it in order.get("items") or []}
    from services import interco_price_service as ips
    planned = _planned(order)
    lines = []
    for b in kurang:
        pid = b["product_id"]
        by = (await availability(pid, buyer)).get("by_entity") or {}
        others = sorted([{"entity_id": e, "entity_name": names.get(e, e), "available": round(q, 2)}
                         for e, q in by.items() if e and e != buyer and q > EPS], key=lambda r: -r["available"])
        for o in others:
            o.update(await ips.price_status(o["entity_id"], buyer, pid))
        lines.append({
            "product_id": pid, "product_name": b.get("product_name"), "sku": b.get("sku"),
            "unit": b.get("unit", "meter"), "backorder_qty": b["backorder_qty"],
            "incoming_total": round(float(b.get("incoming_total") or 0), 2),
            "incoming_claimed_by_older": round(float(b.get("incoming_claimed_by_older") or 0), 2),
            "supply_is_forecast": True,
            "promise_date": b.get("promise_date") or "", "coverage": b.get("coverage", ""),
            "own_available": round(float(by.get(buyer, 0.0)), 2),
            "own_by_warehouse": await _own_by_warehouse(pid, buyer),
            "other_entities": others,
            "proposal": (items.get(pid) or {}).get("fulfillment_proposal") or [],
            "planned_qty": planned.get(pid, 0.0),
        })
    return {"order_id": order["id"], "order_number": order.get("number"),
            "customer_name": order.get("customer_name"), "entity_id": buyer,
            "entity_name": names.get(buyer, buyer), "lines": lines,
            "decision": order.get("fulfillment_decision") or None,
            "decisions": fds.decision_history(order)}


def _validate(lines_in: List[Dict[str, Any]], opts: Dict[str, Any]) -> List[Dict[str, Any]]:
    by_pid = {ln["product_id"]: ln for ln in opts["lines"]}
    plan = []
    seen: set = set()
    for raw in lines_in or []:
        ln = by_pid.get(raw.get("product_id"))
        if not ln:
            raise FulfillmentError("Barang ini tidak (lagi) punya kekurangan di pesanan — muat ulang.")
        nm = ln["product_name"] or ln["product_id"]
        # G3 D4-PLAN-02 — satu baris per produk; dua baris 100+100 tidak boleh lolos kekurangan 100
        if ln["product_id"] in seen:
            raise FulfillmentError(f"{nm}: produk ini muncul lebih dari sekali di rencana — gabungkan jadi satu baris.")
        seen.add(ln["product_id"])
        stock = round(float(raw.get("stock_qty") or 0), 2)
        reorder = round(float(raw.get("reorder_qty") or 0), 2)
        wait = round(float(raw.get("wait_qty") or 0), 2)
        ic_sum: Dict[str, float] = {}
        for x in raw.get("interco") or []:
            if float(x.get("qty") or 0) < 0:
                raise FulfillmentError(f"{nm}: qty tidak boleh negatif.")
            if float(x.get("qty") or 0) > EPS:
                ic_sum[x.get("entity_id")] = round(ic_sum.get(x.get("entity_id"), 0.0) + float(x["qty"]), 2)
        ic = [{"entity_id": e, "qty": q} for e, q in ic_sum.items()]
        if min(stock, reorder, wait) < 0:
            raise FulfillmentError(f"{nm}: qty tidak boleh negatif.")
        total = stock + reorder + wait + sum(x["qty"] for x in ic)
        if total <= EPS:
            continue
        if total > ln["backorder_qty"] + EPS:
            raise FulfillmentError(f"{nm}: total rencana {total:g} melebihi kekurangan {ln['backorder_qty']:g}.")
        if stock > ln["own_available"] + EPS:
            raise FulfillmentError(f"{nm}: stok sendiri hanya {ln['own_available']:g}.")
        if wait > ln["incoming_total"] + EPS:
            raise FulfillmentError(f"{nm}: perkiraan sisa barang datang untuk SO ini hanya {ln['incoming_total']:g} "
                                   "(SO yang lebih lama didahulukan).")
        avail = {o["entity_id"]: o["available"] for o in ln["other_entities"]}
        for x in ic:
            if x["qty"] > avail.get(x["entity_id"], 0.0) + EPS:
                raise FulfillmentError(f"{nm}: stok di PT sumber hanya {avail.get(x['entity_id'], 0.0):g}.")
        plan.append({**ln, "stock": stock, "reorder": reorder, "wait": wait, "interco": ic})
    if not plan:
        raise FulfillmentError("Isi minimal satu qty pemenuhan.")
    return plan


async def _assert_prices(plan: List[Dict[str, Any]], buyer: str) -> None:
    """Tolak SEBELUM ada yang dijalankan bila transfer belum punya harga internal."""
    from services import interco_price_service as ips
    missing: List[Dict[str, Any]] = []
    for ln in plan:
        for x in ln["interco"]:
            missing += await ips.ready_for(x["entity_id"], buyer, [ln["product_id"]]) or []
    if missing:
        skus = ", ".join(m["sku"] or m["product_id"] for m in missing)
        raise FulfillmentError(f"Belum ada harga internal untuk {skus} — buat/minta harga internal dulu, "
                               "lalu jalankan ulang rencana. Belum ada yang dijalankan.",
                               code="INTERCO_PRICE_MISSING", items=missing)


def _row(ln: Dict[str, Any], qty: float) -> Dict[str, Any]:
    return {"product_id": ln["product_id"], "product_name": ln["product_name"],
            "unit": ln["unit"], "backorder_qty": qty, "incoming_total": ln["incoming_total"],
            "promise_date": ln["promise_date"]}


async def _execute(order, plan, actor, note, done: List[Dict[str, Any]]) -> None:
    from services import backorder_service
    for ln in plan:
        if ln["stock"] > EPS:
            got = await backorder_service.fulfill_from_stock(order["id"], ln["product_id"], ln["stock"], actor.get("name", ""))
            done.append({"mode": "stock", "product_id": ln["product_id"], "qty": got, "requested": ln["stock"],
                         "summary": f"{ln['product_name']}: {got:g} dari stok sendiri"})
    by_ent: Dict[str, List[Dict[str, Any]]] = {}
    for ln in plan:
        for x in ln["interco"]:
            by_ent.setdefault(x["entity_id"], []).append(_row(ln, x["qty"]))
    for ent, rows in by_ent.items():
        res = await fds._take_from_other_entity(order, rows, actor, ent, note)
        for r in rows:
            done.append({"mode": "interco", "product_id": r["product_id"], "qty": r["backorder_qty"],
                         "entity_id": ent, "ref_type": res.get("ref_type"), "ref_id": res.get("ref_id"),
                         "ref_number": res.get("ref_number"),
                         "summary": f"{r['product_name']}: {r['backorder_qty']:g} transfer dari PT lain ({res.get('ref_number') or '-'})"})
    rows = [_row(ln, ln["reorder"]) for ln in plan if ln["reorder"] > EPS]
    if rows:
        res = await fds._reorder_supplier(order, rows, actor, note)
        added, existing = res.get("added") or {}, res.get("existing_pr_qty") or {}
        for r in rows:
            pid = r["product_id"]
            got = round(float(added.get(pid, 0.0)), 2)
            summ = (f"{r['product_name']}: {got:g} PO ke supplier ({res.get('ref_number') or '-'})" if got > EPS else
                    f"{r['product_name']}: PR terbuka {res.get('ref_number') or '-'} sudah ada "
                    f"({existing.get(pid, 0):g}) — qty TIDAK ditambah")
            done.append({"mode": "reorder", "product_id": pid, "qty": got, "requested": r["backorder_qty"],
                         "existing_pr_qty": existing.get(pid, 0.0), "reaffirmed": got <= EPS,
                         "ref_type": res.get("ref_type"), "ref_id": res.get("ref_id"), "ref_number": res.get("ref_number"),
                         "summary": summ})
    for ln in plan:
        if ln["wait"] > EPS:
            done.append({"mode": "wait", "product_id": ln["product_id"], "qty": ln["wait"],
                         "promise_date": ln["promise_date"],
                         "summary": f"{ln['product_name']}: {ln['wait']:g} tunggu barang datang (perkiraan, tidak dijamin)"
                                    + (f" (perkiraan {str(ln['promise_date'])[:10]})" if ln["promise_date"] else "")})


async def decide_plan(order_id: str, lines_in: List[Dict[str, Any]], actor: Dict[str, Any],
                      note: str = "") -> Dict[str, Any]:
    order = await fds._order(order_id)
    opts = await plan_options(order)
    plan = _validate(lines_in, opts)
    await _assert_prices(plan, order.get("entity_id") or "")
    done: List[Dict[str, Any]] = []
    error = ""
    try:
        await _execute(order, plan, actor, note, done)
    except FulfillmentError as exc:
        if not done:
            raise
        error = str(exc)
    modes = {p["mode"] for p in done}
    # G3 D4-PLAN-03 — "penuh" dihitung dari qty yang BENAR-BENAR tercatat, bukan qty permintaan;
    # kegagalan sebagian selalu partial dan sisa tetap backorder.
    got: Dict[str, float] = {}
    for p in done:
        got[p["product_id"]] = got.get(p["product_id"], 0.0) + float(p.get("qty") or 0)
    full = (not error and len(plan) == len(opts["lines"])
            and all(abs(got.get(ln["product_id"], 0.0) - ln["backorder_qty"]) <= EPS for ln in plan))
    decision = {
        "mode": next(iter(modes)) if len(modes) == 1 else "split",
        "scope": "full" if full else "partial",
        "by": actor.get("name", ""), "by_id": actor.get("id", ""), "by_role": actor.get("role", ""),
        "at": now_iso(), "note": (note or "").strip()[:400],
        "summary": ("Penuh" if full else "Sebagian") + " — " + "; ".join(p["summary"] for p in done),
        "parts": done, "products": sorted({p["product_id"] for p in done}),
        "error": error or None,
        "remaining": {ln["product_id"]: round(max(0.0, ln["backorder_qty"] - got.get(ln["product_id"], 0.0)), 2)
                      for ln in plan},
        "ref_type": next((p.get("ref_type") for p in done if p.get("ref_type")), ""),
        "ref_id": next((p.get("ref_id") for p in done if p.get("ref_id")), ""),
        "ref_number": next((p.get("ref_number") for p in done if p.get("ref_number")), ""),
    }
    fresh = await fds._order(order_id)
    await fds._record(fresh, decision)
    if error:
        raise FulfillmentError(f"{error} — bagian yang SUDAH dijalankan & tercatat: {decision['summary']}")
    return {"order_id": order_id, "order_number": order.get("number"), "decision": decision,
            "decisions": fds.decision_history(fresh) + [decision]}
