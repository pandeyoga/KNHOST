"""2026-10 — OVERRIDE SO oleh Admin Sales · Manager · Admin, SEBELUM picking.

Header (alamat · metode · tanggal · termin · catatan) dan baris (qty · tambah · hapus)
langsung berlaku dan tercatat sebagai amandemen `auto_applied`. Harga/diskon TIDAK
langsung berlaku: lahir amandemen menunggu pemegang izin `order.approve_price_edit`.
Reservasi mengikuti mesin yang ada (lepas sebagian / alokasi FEFO + backorder).
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from db import db
from core_utils import now_iso, new_id, safe_doc
from services import amendment_service as amd_svc
from services.config_service import compute_order_pricing, get_allocation_policy
from services.roll_service import (allocate_and_reserve_rolls, allocations_from_reserved_rolls,
                                   pending_cuts, release_order_rolls_partial)
from services.so_status import stage_fields

EDITABLE_STATUSES = ("draft", "reserved", "waiting_approval", "approved", "waiting_stock", "confirmed")
HEADER_LABEL = {"shipping_address_id": "Alamat kirim", "fulfillment_method": "Metode pemenuhan",
                "delivery_date": "Tanggal kirim", "pickup_date": "Tanggal ambil",
                "payment_term_code": "Termin bayar", "notes": "Catatan"}
PRICE_FIELDS = ("price", "discount_percent")
EPS = 0.01


class OverrideError(Exception):
    pass


async def lock_reason(order: Dict[str, Any]) -> str:
    """'' bila SO masih boleh di-override; selain itu kalimat alasan terkunci."""
    if order.get("order_type") == "sample":
        return "Pesanan sampel diurus Admin Sampel — tidak lewat override SO."
    if order.get("status") not in EDITABLE_STATUSES:
        return f"Pesanan sudah di tahap '{order.get('status')}' — override hanya sebelum picking."
    started = await db.wms_tasks.find_one(
        {"order_id": order["id"], "flow_type": "outbound",
         "$or": [{"status": {"$nin": ["created", "scheduled", "cancelled"]}}, {"picked_qty": {"$gt": 0}}]},
        {"_id": 0, "id": 1})
    if started:
        return "Gudang sudah mulai picking — SO terkunci."
    issued, why = await amd_svc.is_issued(order)
    if issued:
        return f"Dokumen sudah terbit ({why}) — koreksi lewat amandemen/nota."
    return ""


def _chg(name: str, field: str, label: str, old: Any, new: Any, pid: str = "") -> Dict[str, Any]:
    return {"product_id": pid, "product_name": name, "field": field, "label": label, "from": old, "to": new}


def _check_date(value: str, label: str) -> None:
    if not value:
        return
    try:
        d = datetime.fromisoformat(value).date()
    except ValueError as exc:
        raise OverrideError(f"Format {label.lower()} tidak valid (YYYY-MM-DD).") from exc
    if d < datetime.now(timezone.utc).date():
        raise OverrideError(f"{label} tidak boleh di masa lalu.")


async def _header(order: Dict[str, Any], header: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    patch: Dict[str, Any] = {}
    diff: List[Dict[str, Any]] = []
    for f, label in HEADER_LABEL.items():
        if header.get(f) is None:
            continue
        new, old = str(header[f]).strip(), str(order.get(f) or "")
        if new == old:
            continue
        shown_old, shown_new = old or "—", new or "—"
        if f == "shipping_address_id":
            cust = await db.customers.find_one({"id": order.get("customer_id")}, {"_id": 0, "addresses": 1}) or {}
            addr = next((a for a in cust.get("addresses") or [] if a.get("id") == new), None)
            if not addr:
                raise OverrideError("Alamat tidak ditemukan pada pelanggan ini.")
            patch["shipping_address"] = addr
            shown_old = (order.get("shipping_address") or {}).get("label") or old
            shown_new = addr.get("label") or new
        elif f == "fulfillment_method" and new not in ("kirim", "ambil"):
            raise OverrideError("Metode pemenuhan harus 'kirim' atau 'ambil'.")
        elif f in ("delivery_date", "pickup_date"):
            _check_date(new, label)
        elif f == "payment_term_code":
            from services import entity_master_service as ems
            term = await ems.resolve_row("payment-terms", new, order.get("entity_id") or "")
            if not term:
                raise OverrideError("Termin bayar tidak dikenal.")
            patch["payment_term_name"] = term.get("name", new)
        patch[f] = new
        diff.append(_chg("Pesanan", f, label, shown_old, shown_new))
    method = patch.get("fulfillment_method", order.get("fulfillment_method") or "kirim")
    if method == "ambil" and not patch.get("pickup_date", order.get("pickup_date")):
        raise OverrideError("Order Pengambilan membutuhkan tanggal ambil.")
    return patch, diff


async def _held(order_id: str, pid: str) -> List[Dict[str, Any]]:
    rolls = await db.inventory_rolls.find(
        {"reserved_ref.id": order_id, "product_id": pid, "status": "reserved"}, {"_id": 0}).to_list(1000)
    rolls += [{"id": p["roll_id"], "roll_no": p["roll_no"], "warehouse_id": p["warehouse_id"],
               "owner_entity_id": p["owner_entity_id"], "length_remaining": p["qty"], "lot": p.get("lot"),
               "pending_cut": True, "reservation_id": p["reservation_id"]}
              for p in await pending_cuts(order_id) if p["product_id"] == pid]
    return rolls


def _qty(rolls: List[Dict[str, Any]]) -> float:
    return round(sum(float(r.get("length_remaining") or 0) for r in rolls), 2)


async def _release(order_id: str, pid: str, qty: float) -> None:
    by_wh: Dict[str, float] = {}
    for r in await _held(order_id, pid):
        by_wh[r["warehouse_id"]] = by_wh.get(r["warehouse_id"], 0.0) + float(r.get("length_remaining") or 0)
    left = round(qty, 2)
    for wid, q in sorted(by_wh.items(), key=lambda kv: kv[1]):
        if left <= EPS:
            break
        left = round(left - await release_order_rolls_partial(order_id, pid, wid, round(min(q, left), 2)), 2)


async def _reserve(order: Dict[str, Any], pid: str, qty: float, policy: Dict[str, Any]) -> None:
    await allocate_and_reserve_rolls(pid, round(qty, 2), order.get("customer_city", ""), order["entity_id"],
                                     order["id"], allow_partial=True, policy=policy,
                                     customer_id=order.get("customer_id", ""))


async def _new_item(order: Dict[str, Any], add: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    pid = add["product_id"]
    if any(i.get("product_id") == pid for i in order.get("items") or []):
        raise OverrideError("Produk sudah ada di pesanan — ubah qty barisnya.")
    prod = await db.products.find_one({"id": pid}, {"_id": 0})
    if not prod or prod.get("status") == "inactive":
        raise OverrideError("Produk tidak ditemukan atau nonaktif.")
    from services import costing_service, customer_price_service
    rp = (await customer_price_service.resolve_many(order["entity_id"], order.get("customer_id"),
                                                    [pid], {pid: prod})).get(pid) or {}
    try:
        cost = float((await costing_service.wac_for_product(pid, entity_id=order["entity_id"], product=prod)).get("wac") or 0)
    except Exception:  # noqa: BLE001 — sama dengan pembuatan SO
        cost = 0.0
    unit = prod.get("base_unit", "meter")
    qty = round(float(add["quantity"]), 2)
    return {"product_id": pid, "sku": prod.get("sku", ""), "product_name": prod.get("name", ""),
            "quantity": qty, "unit": unit, "price": round(float(rp.get("price", prod.get("price", 0)) or 0), 2),
            "discount_percent": 0, "qty_rolls": None, "price_source": rp.get("source", "global"),
            "price_record_id": rp.get("record_id") or "", "base_unit": unit, "base_quantity": qty,
            "category": prod.get("category", ""), "line_code": str(prod.get("line_code") or "").strip().lower(),
            "unit_cost": round(cost or float(prod.get("harga_pokok") or 0), 2),
            "added_by_override": actor.get("name", "")}


async def _sync_line(order: Dict[str, Any], item: Dict[str, Any], warehouses: Dict[str, Any],
                     actor_name: str) -> List[Dict[str, Any]]:
    held = await _held(order["id"], item["product_id"])
    reserved = _qty(held)
    bo = round(float(item["base_quantity"]) - reserved - float(item.get("intercompany_pending_qty") or 0), 2)
    item["reserved_qty"] = reserved
    item["backorder_qty"] = bo if bo >= EPS else 0.0
    allocs = allocations_from_reserved_rolls(item["product_id"], held, warehouses, status="allocated")
    for a in allocs:
        a["allocation_explanation"] = f"Disesuaikan lewat override SO oleh {actor_name}."
    return allocs


def _plan_lines(order: Dict[str, Any], lines: List[Dict[str, Any]]):
    by_pid = {i["product_id"]: i for i in order.get("items") or []}
    qty_plan: Dict[str, Any] = {}
    price_changes: List[Dict[str, Any]] = []
    diff: List[Dict[str, Any]] = []
    for ln in lines:
        pid = ln.get("product_id")
        it = by_pid.get(pid)
        if not it:
            raise OverrideError(f"Baris {pid} tidak ada di pesanan.")
        name = it.get("product_name") or it.get("sku") or pid
        if ln.get("remove"):
            qty_plan[pid] = None
            diff.append(_chg(name, "remove", "Hapus baris", float(it.get("quantity") or 0), 0, pid))
            continue
        q = ln.get("quantity")
        if q is not None and abs(float(q) - float(it.get("quantity") or 0)) > 0.0001:
            if float(q) <= 0:
                raise OverrideError(f"{name}: qty harus lebih dari nol (pakai Hapus baris).")
            if it.get("purchase_mode") == "roll":
                raise OverrideError(f"{name}: baris per-roll — qty mengikuti roll yang dipilih (pakai Ganti Roll).")
            qty_plan[pid] = float(q)
            diff.append(_chg(name, "quantity", "Jumlah", float(it.get("quantity") or 0), float(q), pid))
        for f in PRICE_FIELDS:
            if ln.get(f) is not None and abs(float(ln[f]) - float(it.get(f) or 0)) > 0.0001:
                price_changes.append({"product_id": pid, "field": f, "to": float(ln[f])})
    return by_pid, qty_plan, price_changes, diff


async def _regen_tasks(order_id: str, actor_name: str) -> None:
    """SO confirmed (task belum disentuh) → task gudang dilahirkan ulang dari alokasi baru."""
    from services.doc_refs_service import safe_unlink_all
    from services.fulfillment_status import create_outbound_tasks_for_order
    async for t in db.wms_tasks.find({"order_id": order_id, "flow_type": "outbound"}, {"_id": 0, "id": 1}):
        await safe_unlink_all("wms_tasks", t["id"])
    await db.wms_tasks.delete_many({"order_id": order_id, "flow_type": "outbound"})
    await create_outbound_tasks_for_order(order_id, actor_name)


async def _apply_lines(order, items, by_pid, qty_plan, adds, actor, diff) -> Dict[str, Any]:
    customer = await db.customers.find_one({"id": order.get("customer_id")}, {"_id": 0}) or {}
    policy = await get_allocation_policy(order["entity_id"], customer)
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(200)}
    touched = set()
    for pid, q in qty_plan.items():
        it = by_pid[pid]
        held = _qty(await _held(order["id"], pid))
        if q is None:
            await _release(order["id"], pid, held + 1)
            items[:] = [i for i in items if i["product_id"] != pid]
        else:
            oq = float(it.get("quantity") or 0)
            ob = float(it.get("base_quantity") or oq)
            nb = round(q * (ob / oq if oq > 0 else 1.0), 2)
            pend_ic = float(it.get("intercompany_pending_qty") or 0)
            if nb + EPS < held:
                await _release(order["id"], pid, held - nb)
            elif nb > held + pend_ic + EPS:
                await _reserve(order, pid, nb - held - pend_ic, policy)
            it["quantity"], it["base_quantity"] = q, nb
        touched.add(pid)
    for add in adds:
        it = await _new_item({**order, "items": items}, add, actor)
        items.append(it)
        await _reserve(order, it["product_id"], it["base_quantity"], policy)
        touched.add(it["product_id"])
        diff.append(_chg(it["product_name"], "add", "Tambah baris", 0, it["quantity"], it["product_id"]))
    allocations = [a for a in order.get("allocations") or [] if a.get("product_id") not in touched]
    backorders = [b for b in order.get("backorders") or []
                  if b.get("product_id") not in touched or b.get("status") == "fulfilled"]
    for it in items:
        if it["product_id"] not in touched:
            continue
        allocations += await _sync_line(order, it, warehouses, actor.get("name", ""))
        if it["backorder_qty"] > EPS:
            backorders.append({"id": new_id("bo"), "product_id": it["product_id"], "sku": it.get("sku", ""),
                               "product_name": it.get("product_name", ""), "entity_id": order.get("entity_id"),
                               "customer_city": order.get("customer_city", ""),
                               "requested_qty": it["base_quantity"], "reserved_qty": it["reserved_qty"],
                               "backorder_qty": it["backorder_qty"], "status": "waiting_stock",
                               "created_at": now_iso(), "updated_at": now_iso()})
    priced = await compute_order_pricing(items, entity_id=order.get("entity_id") or "",
                                         order_discount_percent=float(order.get("order_discount_percent") or 0),
                                         tax_override=(order.get("tax_override") or None))
    patch = {k: v for k, v in priced.items() if k != "settings"}
    patch.update({"allocations": allocations, "backorders": backorders,
                  "has_backorder": any(float(b.get("backorder_qty") or 0) > EPS for b in backorders),
                  "is_split_warehouse": len({a["warehouse_id"] for a in allocations}) > 1,
                  "has_mixed_lot": any(a.get("lot_mode") == "mixed" for a in allocations)})
    if order["status"] in ("reserved", "waiting_stock"):
        total = sum(float(i.get("reserved_qty") or 0) for i in patch.get("items") or items)
        patch["status"] = "reserved" if total > EPS else "waiting_stock"
    return patch


async def apply(order_id: str, body: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    from services import atomic_claim as saga
    order = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    if not order:
        raise OverrideError("Pesanan tidak ditemukan.")
    why = await lock_reason(order)
    if why:
        raise OverrideError(why)
    note = (body.get("note") or "").strip()
    if len(note) < 5:
        raise OverrideError("Alasan override wajib diisi (minimal 5 karakter).")
    hdr_patch, diff = await _header(order, body.get("header") or {})
    by_pid, qty_plan, price_changes, line_diff = _plan_lines(order, body.get("lines") or [])
    diff += line_diff
    adds = [a for a in body.get("add_items") or [] if float(a.get("quantity") or 0) > 0]
    price_changes = [c for c in price_changes if qty_plan.get(c["product_id"], 1) is not None]
    if not (hdr_patch or qty_plan or adds or price_changes):
        raise OverrideError("Tidak ada perubahan.")
    if sum(1 for p in by_pid if qty_plan.get(p, 1) is not None) + len(adds) == 0:
        raise OverrideError("Pesanan minimal punya satu baris — batalkan SO bila semua dihapus.")
    if price_changes:   # validasi dulu supaya tidak ada yang setengah jalan
        await amd_svc.preview("sales_order", order_id, price_changes, "admin_override_price")

    if hdr_patch.get("shipping_address"):
        order["customer_city"] = hdr_patch["shipping_address"].get("city") or order.get("customer_city", "")
        hdr_patch["customer_city"] = order["customer_city"]
    line_touch = bool(qty_plan or adds)
    if hdr_patch or line_touch:
        await saga.claim("sales_orders", order_id, "so_override",
                         precondition={"status": order["status"]}, actor=actor.get("name", ""))
        try:
            patch = dict(hdr_patch)
            if line_touch:
                items = [dict(i) for i in order.get("items") or []]
                by_pid = {i["product_id"]: i for i in items}
                patch.update(await _apply_lines(order, items, by_pid, qty_plan, adds, actor, diff))
            now = now_iso()
            patch.update({"updated_at": now, "last_override_at": now, "last_override_by": actor.get("name", "")})
            patch.update(stage_fields({**order, **patch}))
            await db.sales_orders.update_one({"id": order_id}, saga.finish_set(patch))
        except Exception:
            await saga.release("sales_orders", order_id)
            raise
        if line_touch and order["status"] == "confirmed":
            await _regen_tasks(order_id, actor.get("name", ""))

    fresh = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    event = None
    if diff:
        event = await amd_svc.record_event(fresh, "admin_override", "Override SO oleh Admin", diff, actor, note,
                                           before_total=order.get("grand_total"),
                                           after_total=fresh.get("grand_total"))
    pending = await amd_svc.propose_price_edit(order_id, price_changes, actor, note) if price_changes else None
    parts = [f"{len(diff)} perubahan langsung berlaku"] if diff else []
    if pending:
        parts.append(f"harga/diskon menunggu persetujuan ({pending['number']})")
    await notify_sales(fresh, actor, f"{fresh.get('number')} diubah oleh {actor.get('name', 'Admin')}",
                       "; ".join(parts) + f". Alasan: {note}")
    return {"order": safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0})),
            "amendment": event, "price_amendment": pending, "changes": diff}


async def notify_sales(order: Dict[str, Any], actor: Dict[str, Any], title: str, body: str) -> None:
    """Pemberitahuan di aplikasi ke sales pemilik pesanan (tanpa email/WA)."""
    from services import notification_service as ns
    ids = {str(m.get("sales_id")) for m in order.get("sales_team") or [] if m.get("sales_id")}
    ids.update(str(order[k]) for k in ("sales_id", "created_by") if order.get(k))
    ids.discard(str(actor.get("id") or ""))
    for uid in ids:
        await ns.create_notification(notif_type="so_override", title=title, body=body[:400], severity="info",
                                     link="orders", entity_id=order.get("entity_id") or None,
                                     recipient_role="", recipient_user=uid, dedupe=False)
