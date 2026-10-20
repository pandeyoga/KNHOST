"""L03 LN-033 — rute pemenuhan per item Pesanan Khusus: supplier (PR→PO) atau makloon (PR→MKO).

Satu layanan routing dipakai create-pr manual, auto-procure saat kunci harga, dan retry.
Status disimpan di `special_orders.fulfillment.<item_key>`; field lama `linked_pr_id`/`linked_po_id`
tetap diisi untuk kompatibilitas pembacaan. Tidak ada ledger reservasi lokal: bahan memakai
`material_reservation_service`; dokumen memakai PR/PO/MKO existing.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from db import db
from core_utils import new_id, now_iso, rupiah

logger = logging.getLogger(__name__)

LEGACY_KEY = "main"
ROUTES = ("purchase", "makloon")
ROUTE_LABEL = {"purchase": "Supplier (PR → PO)", "makloon": "Makloon (PR → MKO)"}
MODE_TO_ROUTE = {"supplier": "purchase", "makloon": "makloon"}
LOCK_TTL_S = 120
PO_DEAD = ("cancelled", "rejected")
MKO_DEAD = ("cancelled",)


class FulfillmentError(ValueError):
    pass


class FulfillmentConflict(FulfillmentError):
    pass


def _label(od: Dict[str, Any]) -> str:
    return f"Pesanan Khusus {od.get('number') or od.get('id')}"


# ─── Kebutuhan per item ──────────────────────────────────────────────────────
async def _item_decision(od: Dict[str, Any], item_id: str) -> Dict[str, Any]:
    q: Dict[str, Any] = {"special_order_id": od["id"], "status": "decided"}
    if item_id:
        q["special_order_item_id"] = item_id
    rows = await db.md_samples.find(q, {"_id": 0, "number": 1, "decision": 1, "created_at": 1}).to_list(50)
    rows = [r for r in rows if (r.get("decision") or {}).get("product_id")]
    rows.sort(key=lambda r: r.get("created_at") or "")
    return ({**rows[-1]["decision"], "sample_number": rows[-1].get("number", "")}) if rows else {}


async def _default_route(product: Dict[str, Any]) -> Dict[str, Any]:
    tpl = await db.product_templates.find_one({"id": product.get("template_id") or "__none__"},
                                              {"_id": 0, "id": 1, "name": 1, "restock_source": 1}) or {}
    mode = (tpl.get("restock_source") or {}).get("mode") or ""
    return {"source_mode": mode or "unmapped", "default_route": MODE_TO_ROUTE.get(mode, ""),
            "template_id": tpl.get("id", ""), "article": tpl.get("name", "")}


async def needs(od: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Kebutuhan pemenuhan: satu per item (OD multi-item) atau satu `main` (OD lama)."""
    pricing = od.get("pricing") or {}
    all_items = list(od.get("items") or [])
    # FE-01 lanjutan — item yang dibatalkan tidak lagi dipenuhi/dihargai.
    items = [it for it in all_items if it.get("status") != "cancelled"]
    raw: List[Dict[str, Any]] = []
    if all_items:
        for it in items:
            dec = await _item_decision(od, it["id"])
            if not dec and len(all_items) == 1:
                dec = {k: pricing.get(k) for k in ("product_id", "product_sku", "supplier_id", "supplier_name", "contract_number", "sample_number")}
                dec["price"] = pricing.get("cost_price")
            raw.append({"key": it["id"], "item_id": it["id"], "line_no": it.get("line_no"), "description": it.get("description", ""),
                        "quantity": float(it.get("quantity") or 0), "unit": it.get("unit") or "meter", "decision": dec or {}})
    else:
        ci = od.get("custom_item") or {}
        dec = {k: pricing.get(k) for k in ("product_id", "product_sku", "supplier_id", "supplier_name", "contract_number", "sample_number")}
        dec["price"] = pricing.get("cost_price")
        if not dec.get("product_id"):
            dec["product_id"] = od.get("linked_product_id") or ""
        raw.append({"key": LEGACY_KEY, "item_id": "", "line_no": 1, "description": od.get("title") or ci.get("description", ""),
                    "quantity": float(pricing.get("quantity") or ci.get("quantity") or 0),
                    "unit": pricing.get("unit") or ci.get("unit") or "meter", "decision": dec})
    state_all = od.get("fulfillment") or {}
    out = []
    for n in raw:
        dec = n.pop("decision")
        pid = dec.get("product_id") or ""
        prod = await db.products.find_one({"id": pid}, {"_id": 0, "id": 1, "sku": 1, "name": 1, "lifecycle": 1, "spec_id": 1,
                                                        "template_id": 1, "stage": 1, "base_unit": 1}) if pid else None
        dflt = await _default_route(prod) if prod else {"source_mode": "unmapped", "default_route": "", "template_id": "", "article": ""}
        st = dict(state_all.get(n["key"]) or {})
        if not st and n["key"] == LEGACY_KEY and od.get("linked_po_id"):
            st = {"route": "purchase", "legacy": True, "pr_id": od.get("linked_pr_id", ""), "pr_number": od.get("linked_pr_number", ""),
                  "docs": [{"type": "po", "id": od["linked_po_id"], "number": od.get("linked_po_number", "")}]}
        route = st.get("route") or ""
        out.append({**n, "product_id": pid, "product_sku": (prod or {}).get("sku") or dec.get("product_sku", ""),
                    "product_name": (prod or {}).get("name", ""), "product_lifecycle": (prod or {}).get("lifecycle", ""),
                    "spec_id": (prod or {}).get("spec_id", ""),
                    "supplier_id": dec.get("supplier_id", ""), "supplier_name": dec.get("supplier_name", ""),
                    "cost_price": float(dec.get("price") or 0), "contract_number": dec.get("contract_number", ""),
                    "sample_number": dec.get("sample_number", ""), **dflt,
                    "route": route, "effective_route": route or dflt["default_route"], "state": st})
    return out


def _need(rows: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    n = next((r for r in rows if r["key"] == key), None)
    if not n:
        raise FulfillmentError("Item pemenuhan tidak ditemukan pada Pesanan Khusus ini.")
    return n


# ─── Status dokumen ──────────────────────────────────────────────────────────
async def _doc_status(d: Dict[str, Any]) -> Dict[str, Any]:
    if d.get("type") == "po":
        po = await db.purchase_orders.find_one({"id": d["id"]}, {"_id": 0, "po_number": 1, "status": 1, "items": 1, "supplier_name": 1}) or {}
        recv = sum(float(i.get("received_qty") or 0) for i in po.get("items") or [] if i.get("product_id") == d.get("product_id"))
        return {**d, "status": po.get("status", "missing"), "partner_name": po.get("supplier_name", ""),
                "received_qty": round(recv, 3), "active": bool(po) and po.get("status") not in PO_DEAD,
                "issued": recv > 0}
    if d.get("type") == "mko":
        mk = await db.makloon_orders.find_one({"id": d["id"]}, {"_id": 0, "mko_number": 1, "status": 1, "steps": 1,
                                                                 "forecast": 1, "actual_output_qty": 1}) or {}
        steps = mk.get("steps") or []
        issued = any(s.get("status") in ("issued", "received", "returned") for s in steps)
        res = await db.material_reservations.find_one({"ref_id": d["id"], "status": {"$in": ["active", "consumed"]}},
                                                      {"_id": 0, "required_qty": 1, "qty": 1, "shortage_qty": 1}) or {}
        return {**d, "status": mk.get("status", "missing"), "active": bool(mk) and mk.get("status") not in MKO_DEAD,
                "issued": issued, "partner_name": next((s.get("makloon_name") for s in steps if s.get("makloon_name")), ""),
                "expected_output_qty": float((mk.get("forecast") or {}).get("expected_finished_qty") or 0),
                "received_qty": float(mk.get("actual_output_qty") or 0),
                "material_required": float(res.get("required_qty") or 0), "material_reserved": float(res.get("qty") or 0),
                "material_shortage": float(res.get("shortage_qty") or 0)}
    return {**d, "active": False}


async def progress(od: Dict[str, Any]) -> Dict[str, Any]:
    rows = await needs(od)
    for n in rows:
        st = n["state"]
        docs = [await _doc_status(d) for d in st.get("docs") or []]
        n["docs"] = docs
        n["active_docs"] = [d for d in docs if d.get("active")]
        n["history_docs"] = st.get("history_docs") or []
        n["route_history"] = st.get("history") or []
        if st.get("pr_id"):
            pr = await db.purchase_requisitions.find_one({"id": st["pr_id"]}, {"_id": 0, "number": 1, "status": 1})
            n["pr"] = {"id": st["pr_id"], "number": (pr or {}).get("number", st.get("pr_number", "")), "status": (pr or {}).get("status", "missing")}
        n["blockers"] = await _blockers(od, n)
        from services import rnd_revalidation_service as _rv
        n["revalidation"] = await _rv.latest_for(n["product_id"], n["supplier_id"])
        n["warnings"] = _warnings(n)
        n["status"] = _need_status(n)
        n["error"] = st.get("error", "")
    agg = "realized" if rows and all(r["status"] in ("realized", "waiting_material") for r in rows) else (
        "partial" if any(r["active_docs"] for r in rows) else "not_started")
    return {"special_order_id": od["id"], "number": od.get("number", ""), "aggregate": agg, "items": rows,
            "routes": [{"value": k, "label": v} for k, v in ROUTE_LABEL.items()]}


def _warnings(n: Dict[str, Any]) -> List[str]:
    """Forecast makloon < kebutuhan → sisa kebutuhan terlihat (tindak lanjut lewat amandemen/permintaan tambahan)."""
    out = []
    rv = n.get("revalidation") or {}
    if (rv.get("state") or "").startswith("fail"):
        out.append(f"Uji ulang terbaru {n['product_sku']} × {n['supplier_name']} ({rv.get('number')}): {rv.get('state_label')} — "
                   "bukan bukti lulus untuk pengadaan baru; pekerjaan existing tidak dihentikan otomatis.")
    for d in n["active_docs"]:
        exp = float(d.get("expected_output_qty") or 0)
        if d.get("type") == "mko" and 0 < exp < n["quantity"] - 0.001:
            out.append(f"Estimasi hasil {d['number']} {exp:g} < kebutuhan {n['quantity']:g} {n['unit']} — sisa "
                       f"{n['quantity'] - exp:g} {n['unit']} belum tercakup; periksa resep/satuan bahan atau ajukan tambahan.")
    return out


def _need_status(n: Dict[str, Any]) -> str:
    if n["active_docs"]:
        if any(d.get("material_shortage", 0) > 0 for d in n["active_docs"]):
            return "waiting_material"
        return "realized"
    if n["state"].get("status") == "needs_data":
        return "needs_data"
    if n["state"].get("error"):
        return "error"
    if n["blockers"]:
        return "blocked"
    return "ready"


async def _blockers(od: Dict[str, Any], n: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    if not (od.get("pricing") or {}).get("locked"):
        out.append("Harga final belum dikunci (ACC pelanggan + margin).")
    if not n["product_id"]:
        out.append("SKU hasil belum lahir — selesaikan uji & ACC spesifikasi pada keputusan sample item ini.")
    if not n["effective_route"]:
        out.append("Jalur pemenuhan belum dipilih" + (" — sumber restock artikel belum diatur di master."
                                                      if n["source_mode"] == "unmapped" else " — artikel bisa supplier atau makloon."))
    if n["effective_route"] == "purchase" and not n["supplier_id"]:
        out.append("Supplier pemenang belum diketahui untuk jalur supplier.")
    return out


# ─── Izin ────────────────────────────────────────────────────────────────────
async def _can(user: Dict[str, Any], action: str) -> bool:
    from dependencies import has_permission
    return await has_permission(user, "od_fulfillment", action)


async def _require(user: Dict[str, Any], action: str, what: str) -> None:
    if not await _can(user, action):
        raise PermissionError(f"Permission ditolak: od_fulfillment.{action} ({what}).")


# ─── Pilih / ubah jalur ──────────────────────────────────────────────────────
async def set_route(od: Dict[str, Any], key: str, route: str, reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    await _require(actor, "choose_route", "memilih jalur pemenuhan")
    if route not in ROUTES:
        raise FulfillmentError("Jalur harus 'purchase' (supplier) atau 'makloon'.")
    if od.get("status") in ("cancelled", "done", "shipped"):
        raise FulfillmentError("Pesanan Khusus sudah selesai/batal — jalur tidak bisa diubah.")
    n = _need(await needs(od), key)
    reason = (reason or "").strip()
    deviation = bool(n["default_route"]) and route != n["default_route"]
    if deviation:
        await _require(actor, "override_default", "menyimpang dari sumber default master")
        if not reason:
            raise FulfillmentError(f"Default master artikel {n['article'] or n['product_sku']} adalah "
                                   f"{ROUTE_LABEL[n['default_route']]} — tulis alasan memilih {ROUTE_LABEL[route]}.")
    if n["source_mode"] in ("both", "unmapped") and not reason:
        reason = f"Dipilih {actor.get('name', '')} (sumber master: {n['source_mode']})"
    st = dict(n["state"])
    if st.get("route") == route:
        return st
    docs = [await _doc_status(d) for d in st.get("docs") or []]
    live = [d for d in docs if d.get("active")]
    if live:
        nums = ", ".join(d.get("number") or d["id"] for d in live)
        extra = " Bahan sudah di-issue ke mitra — selesaikan retur/rekonsiliasi bahan dulu." if any(d.get("issued") for d in live) else ""
        raise FulfillmentConflict(f"Dokumen pengadaan {nums} masih aktif — batalkan/amandemen lewat modul PO/Order Makloon "
                                  f"sebelum mengganti jalur.{extra}")
    ver = int(st.get("version") or 0) + 1
    hist = {"at": now_iso(), "by": actor.get("name", ""), "before": st.get("route") or n["default_route"] or "",
            "after": route, "reason": reason, "deviation": deviation, "version": ver}
    upd = {f"fulfillment.{key}.route": route, f"fulfillment.{key}.default_route": n["default_route"],
           f"fulfillment.{key}.source_mode": n["source_mode"], f"fulfillment.{key}.reason": reason,
           f"fulfillment.{key}.deviation": deviation, f"fulfillment.{key}.version": ver,
           f"fulfillment.{key}.decided_by": actor.get("name", ""), f"fulfillment.{key}.decided_at": hist["at"],
           f"fulfillment.{key}.error": "", f"fulfillment.{key}.status": "planned", "updated_at": now_iso()}
    if docs:   # dokumen lama yang sudah batal tetap auditable
        upd[f"fulfillment.{key}.docs"] = []
        upd[f"fulfillment.{key}.pr_id"] = ""
        upd[f"fulfillment.{key}.pr_number"] = ""
    push: Dict[str, Any] = {f"fulfillment.{key}.history": hist,
                            "status_history": {"status": od.get("status"), "timestamp": hist["at"], "user": actor.get("email", ""),
                                               "note": f"Jalur pemenuhan {n['description'] or n['product_sku']}: {ROUTE_LABEL[route]}"
                                                       + (f" (menyimpang dari default; {reason})" if deviation else "")}}
    if docs:
        push[f"fulfillment.{key}.history_docs"] = {"$each": [{**d, "archived_at": hist["at"]} for d in docs]}
    old_pr = st.get("pr_id") or ""
    if old_pr:   # PR jalur lama tidak dipakai jalur baru; batal bila belum terminal, jejak tetap ada
        upd[f"fulfillment.{key}.pr_id"] = ""
        upd[f"fulfillment.{key}.pr_number"] = ""
        push.setdefault(f"fulfillment.{key}.history_docs", {"$each": []})["$each"].append(
            {"type": "pr", "id": old_pr, "number": st.get("pr_number", ""), "archived_at": hist["at"]})
    res = await db.special_orders.update_one({"id": od["id"], f"fulfillment.{key}.version": st.get("version") if st.get("version") else {"$exists": False}},
                                             {"$set": upd, "$push": push})
    if res.matched_count == 0:
        raise FulfillmentConflict("Jalur baru saja diubah pengguna lain — muat ulang.")
    if old_pr:
        await db.purchase_requisitions.update_one({"id": old_pr}, {"$set": {"source_item_key": f"{key}#retired"}})
        from services import purchase_requisition_service as pr_svc
        try:
            await pr_svc.cancel_requisition(old_pr)
        except ValueError as exc:
            logger.info("[fulfillment.set_route] PR lama %s tidak dibatalkan: %s", old_pr, exc)
    return (await db.special_orders.find_one({"id": od["id"]}, {"_id": 0, "fulfillment": 1}))["fulfillment"][key]


# ─── Kunci operasi per item ──────────────────────────────────────────────────
async def _claim(od_id: str, key: str, actor: str) -> str:
    """Kunci realisasi per item ber-LEASE (LOCK_TTL_S). AUD-SO-01 — kunci membawa TOKEN pemegang: proses
    yang lease-nya sudah kedaluwarsa tidak bisa lagi melepas/memperpanjang kunci milik proses baru."""
    stale = (datetime.now(timezone.utc) - timedelta(seconds=LOCK_TTL_S)).isoformat()
    path = f"fulfillment_locks.{key}"
    token = new_id("flk")
    res = await db.special_orders.update_one(
        {"id": od_id, "$or": [{path: {"$exists": False}}, {f"{path}.at": {"$lt": stale}}]},
        {"$set": {path: {"at": now_iso(), "by": actor, "token": token}}})
    if res.matched_count == 0:
        raise FulfillmentConflict("Realisasi item ini sedang diproses pengguna lain — tunggu sebentar lalu muat ulang.")
    return token


async def _renew(od_id: str, key: str, token: str) -> None:
    """Perpanjang lease HANYA bila kunci masih milik token ini; kalau sudah diambil proses lain, hentikan
    sebelum dokumen pengadaan dibuat (mencegah PR/PO/MKO ganda)."""
    path = f"fulfillment_locks.{key}"
    res = await db.special_orders.update_one({"id": od_id, f"{path}.token": token}, {"$set": {f"{path}.at": now_iso()}})
    if res.matched_count == 0:
        raise FulfillmentConflict("Kunci realisasi item ini sudah diambil proses lain (proses ini terlalu lama) — "
                                  "muat ulang dan periksa dokumen yang terbentuk.")


async def _release(od_id: str, key: str, token: str) -> None:
    """Lepas kunci HANYA bila masih milik token ini (bukan kunci proses lain yang mengambil alih)."""
    path = f"fulfillment_locks.{key}"
    await db.special_orders.update_one({"id": od_id, f"{path}.token": token}, {"$unset": {path: ""}})


async def _save(od_id: str, key: str, fields: Dict[str, Any]) -> None:
    await db.special_orders.update_one({"id": od_id}, {"$set": {**{f"fulfillment.{key}.{k}": v for k, v in fields.items()},
                                                               "updated_at": now_iso()}})


# ─── Rilis master (tanpa fallback lifecycle) ─────────────────────────────────
async def ensure_released(n: Dict[str, Any], actor: Dict[str, Any], od: Dict[str, Any]) -> None:
    if n["product_lifecycle"] in ("", None, "produksi"):
        return
    if not n["spec_id"]:
        raise FulfillmentError(f"SKU {n['product_sku']} belum dirilis dan tidak punya spesifikasi — rilis lewat R&D dulu.")
    from services import rnd_spec_service as spec_svc
    try:
        await spec_svc.release_product(n["spec_id"], actor, note=f"Pemenuhan {_label(od)}")
    except Exception as exc:  # noqa: BLE001 — guard uji/spesifikasi tidak boleh dilewati
        detail = getattr(exc, "detail", None) or str(exc)
        raise FulfillmentError(f"Rilis master SKU {n['product_sku']} ditolak: {detail}") from exc


# ─── PR (create-pr manual & otomatis memakai jalur yang sama) ────────────────
async def _find_pr(od_id: str, key: str, st: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if st.get("pr_id"):
        pr = await db.purchase_requisitions.find_one({"id": st["pr_id"]}, {"_id": 0})
        if pr and pr.get("status") not in ("cancelled", "rejected"):
            return pr
    q = {"source": "special_order", "source_ref_id": od_id, "source_item_key": key, "status": {"$nin": ["cancelled", "rejected"]}}
    return await db.purchase_requisitions.find_one(q, {"_id": 0})


async def ensure_pr(od: Dict[str, Any], n: Dict[str, Any], route: str, actor: Dict[str, Any], warehouse_id: str,
                    *, submit_now: bool = True, est_price: float = 0, notes: str = "", needed_by: str = "") -> Dict[str, Any]:
    pr = await _find_pr(od["id"], n["key"], n["state"])
    if not pr and n["key"] == LEGACY_KEY and od.get("linked_pr_id"):
        pr = await db.purchase_requisitions.find_one({"id": od["linked_pr_id"], "status": {"$nin": ["cancelled", "rejected"]}}, {"_id": 0})
    if pr:
        await _save(od["id"], n["key"], {"pr_id": pr["id"], "pr_number": pr.get("number", ""), "route": route})
        return pr
    from services import purchase_requisition_service as pr_svc
    from schemas import PurchaseRequisitionCreate, PurchaseRequisitionItem
    reason = n["state"].get("reason") or ""
    pr = await pr_svc.create_requisition(PurchaseRequisitionCreate(
        items=[PurchaseRequisitionItem(product_id=n["product_id"], description=n["description"], quantity=n["quantity"],
                                       unit=n["unit"], est_price=float(est_price or n["cost_price"] or 0), fulfillment_mode=route,
                                       note=f"Kontrak {n['contract_number'] or '-'} · sample {n['sample_number'] or '-'}")],
        warehouse_id=warehouse_id, entity_id=od.get("entity_id", ""), route_reason=reason,
        reason=f"Pemenuhan {_label(od)} item {n['line_no']} — {ROUTE_LABEL[route]}",
        needed_by_date=needed_by or od.get("expected_delivery", ""), source="special_order", source_ref_id=od["id"],
        notes=notes, submit_now=submit_now), created_by=actor.get("name", "Sistem (OD)"))
    await db.purchase_requisitions.update_one({"id": pr["id"]}, {"$set": {"source_item_key": n["key"],
                                                                         "special_order_item_id": n["item_id"]}})
    await _save(od["id"], n["key"], {"pr_id": pr["id"], "pr_number": pr["number"], "route": route})
    legacy = {} if od.get("linked_pr_id") else {"linked_pr_id": pr["id"], "linked_pr_number": pr["number"], "pr_id": pr["id"]}
    if legacy:
        await db.special_orders.update_one({"id": od["id"]}, {"$set": legacy})
    return pr


# ─── Realisasi ───────────────────────────────────────────────────────────────
async def realize(od: Dict[str, Any], key: str, actor: Dict[str, Any], warehouse_id: str = "",
                  *, check_perm: bool = True) -> Dict[str, Any]:
    if check_perm:
        await _require(actor, "realize", "merealisasi pengadaan")
    n = _need(await needs(od), key)
    for d in n["state"].get("docs") or []:
        if (await _doc_status(d)).get("active"):
            return {"key": key, "skipped": "sudah terealisasi", "docs": n["state"]["docs"]}
    blockers = await _blockers(od, n)
    if blockers:
        raise FulfillmentError(" ".join(blockers))
    route = n["effective_route"]
    token = await _claim(od["id"], key, actor.get("name", ""))
    try:
        # AUD-SO-01 — validasi ulang SESUDAH kunci diperoleh: proses lain bisa saja sudah merealisasi item ini
        # selagi kita menunggu/menyiapkan.
        fresh = await db.special_orders.find_one({"id": od["id"]}, {"_id": 0})
        for d in ((fresh or {}).get("fulfillment") or {}).get(key, {}).get("docs") or []:
            if (await _doc_status(d)).get("active"):
                return {"key": key, "skipped": "sudah terealisasi", "docs": fresh["fulfillment"][key]["docs"]}
        if not n["route"]:   # default master dipakai — dicatat eksplisit
            await _save(od["id"], key, {"route": route, "default_route": n["default_route"], "source_mode": n["source_mode"],
                                        "reason": "", "deviation": False, "version": 1, "decided_by": actor.get("name", ""),
                                        "decided_at": now_iso(), "status": "planned"})
            n["state"] = {**n["state"], "route": route, "version": 1}
        await ensure_released(n, actor, od)
        await _renew(od["id"], key, token)
        from services import special_order_phase2 as p2
        wh = warehouse_id or od.get("procurement_warehouse_id") or await p2.default_warehouse_id(od.get("entity_id", ""))
        if not wh:
            raise FulfillmentError("Tidak ada gudang aktif untuk badan usaha ini — pilih gudang tujuan.")
        from services import warehouse_scope_service as whs
        await whs.assert_usable(wh, od.get("entity_id", ""), action="menerima barang di sini", field_label="Gudang tujuan")
        await _renew(od["id"], key, token)
        pr = await ensure_pr(od, n, route, actor, wh)
        from services import purchase_requisition_service as pr_svc
        if pr.get("status") in ("draft", "pending_approval"):
            try:
                await pr_svc.approve_requisition(pr["id"], actor, notes=f"Otomatis — pemenuhan {_label(od)}")
            except ValueError as exc:
                raise FulfillmentError(f"PR {pr.get('number')} belum bisa disetujui otomatis: {exc}") from exc
        await _renew(od["id"], key, token)
        doc = await (_realize_po(od, n, pr["id"], wh, actor) if route == "purchase" else _realize_mko(od, n, pr["id"], actor))
        if doc is None:
            return {"key": key, "status": "needs_data", "pr_number": pr.get("number")}
        from services import rnd_revalidation_service as _rv   # L03 LN-034 — referensi hasil uji per produk/supplier/versi
        doc["revalidation_ref"] = await _rv.latest_for(n["product_id"], n["supplier_id"])
        await db.special_orders.update_one({"id": od["id"]}, {
            "$set": {f"fulfillment.{key}.status": "realized", f"fulfillment.{key}.error": "",
                     "procurement_warehouse_id": wh, "procurement_error": "", "updated_at": now_iso(),
                     **({"linked_po_id": doc["id"], "linked_po_number": doc["number"]} if doc["type"] == "po" and not od.get("linked_po_id") else {}),
                     **({"linked_mko_id": doc["id"], "linked_mko_number": doc["number"]} if doc["type"] == "mko" and not od.get("linked_mko_id") else {})},
            "$push": {f"fulfillment.{key}.docs": doc,
                      "status_history": {"status": od.get("status"), "timestamp": now_iso(), "user": actor.get("email", ""),
                                         "note": f"Item {n['line_no']}: PR {pr.get('number')} → {doc['type'].upper()} {doc['number']} ({ROUTE_LABEL[route]})"}}})
        if od.get("status") == "confirmed":
            from services.special_order_service import transition_special_order_status
            try:
                await transition_special_order_status(od["id"], "in_production", actor.get("email", ""))
            except ValueError as exc:
                logger.warning("[fulfillment.realize] transisi status diabaikan: %s", exc)
        return {"key": key, "pr_id": pr["id"], "pr_number": pr.get("number"), "doc": doc, "warehouse_id": wh}
    except Exception as exc:
        await _save(od["id"], key, {"error": getattr(exc, "detail", None) or str(exc), "error_at": now_iso()})
        raise
    finally:
        await _release(od["id"], key, token)


async def _realize_po(od, n, pr_id, wh, actor) -> Dict[str, Any]:
    existing = await db.purchase_orders.find_one({"special_order_id": od["id"], "special_order_item_key": n["key"],
                                                  "status": {"$nin": list(PO_DEAD)}}, {"_id": 0, "id": 1, "po_number": 1})
    if not existing:
        pr = await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0, "items": 1})
        rz = [r for it in (pr or {}).get("items") or [] for r in it.get("realizations") or [] if r.get("kind") in ("po", "purchase_order")]
        if rz:
            existing = await db.purchase_orders.find_one({"id": rz[-1].get("ref_id"), "status": {"$nin": list(PO_DEAD)}},
                                                         {"_id": 0, "id": 1, "po_number": 1})
    if existing:
        po = existing
    else:
        from services import purchase_requisition_service as pr_svc
        try:
            res = await pr_svc.convert_to_po(pr_id, n["supplier_id"], actor, warehouse_id=wh,
                                             expected_delivery_date=od.get("expected_delivery", ""),
                                             notes=f"Otomatis dari {_label(od)} · kontrak {n['contract_number'] or '-'}")
        except ValueError as exc:
            raise FulfillmentError(str(exc)) from exc
        po = res.get("po") or {}
        await _fix_po_price(po.get("id", ""), n, od)
    await db.purchase_orders.update_one({"id": po["id"]}, {"$set": {
        "special_order_id": od["id"], "special_order_number": od.get("number", ""), "special_order_item_key": n["key"],
        "special_order_item_id": n["item_id"], "exclusive_customer_id": od.get("customer_id", ""),
        "exclusive_customer_name": od.get("customer_name", "")}})
    return {"type": "po", "id": po["id"], "number": po.get("po_number", ""), "pr_id": pr_id, "product_id": n["product_id"],
            "quantity": n["quantity"], "unit": n["unit"], "created_at": now_iso()}


async def _fix_po_price(po_id: str, n: Dict[str, Any], od: Dict[str, Any]) -> None:
    """Harga PO = harga kontrak pemenang yang dikunci (bukan kontrak lain supplier yang sama)."""
    cost = float(n["cost_price"] or 0)
    po_doc = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0, "items": 1}) or {}
    if cost <= 0 or not po_doc.get("items"):
        return
    items, changed = po_doc["items"], False
    for it in items:
        if it.get("product_id") == n["product_id"] and abs(float(it.get("price") or it.get("unit_price") or 0) - cost) > 0.009:
            q = float(it.get("quantity") or 0)
            it.update({"price": cost, "unit_price": cost, "subtotal": round(cost * q, 2),
                       "contract_number": n["contract_number"] or it.get("contract_number", ""), "price_source": "special_order_contract"})
            changed = True
    if changed:
        from services.config_service import compute_order_pricing
        pr_ = await compute_order_pricing([dict(i) for i in items], od.get("entity_id", ""), 0.0, cfg_section="purchasing")
        await db.purchase_orders.update_one({"id": po_id}, {"$set": {
            "items": pr_["items"], "total_amount": pr_["total_amount"], "net_subtotal": pr_["net_subtotal"], "dpp": pr_["dpp"],
            "ppn_amount": pr_["ppn_amount"], "grand_total": pr_["grand_total"], "outstanding": round(float(pr_["grand_total"]), 2),
            "approval_amount": pr_["total_amount"], "updated_at": now_iso()}})


async def _realize_mko(od, n, pr_id, actor) -> Optional[Dict[str, Any]]:
    from services import pr_sourcing_service as srcg
    pr = await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0, "items": 1, "number": 1})
    line = ((pr or {}).get("items") or [{}])[0]
    rz = [r for r in line.get("realizations") or [] if r.get("kind") == "makloon_order"]
    mko = await db.makloon_orders.find_one({"id": rz[-1]["ref_id"], "status": {"$nin": list(MKO_DEAD)}},
                                           {"_id": 0, "id": 1, "mko_number": 1}) if rz else None
    if not mko:
        pre = await srcg.makloon_prefill(pr_id, int(line.get("line_no") or 1))
        if not pre.get("ready"):
            msg = (pre.get("reason") or "Data makloon belum lengkap — lengkapi resep proses/mitra di master.") + " Lalu ulangi realisasi."
            await _save(od["id"], n["key"], {"status": "needs_data", "error": msg, "error_at": now_iso()})
            return None
        try:
            res = await srcg.realize_to_makloon(pr_id, int(line.get("line_no") or 1), {}, actor)
        except srcg.SourcingError as exc:
            raise FulfillmentError(str(exc)) from exc
        mko = res["makloon_order"]
    await db.makloon_orders.update_one({"id": mko["id"]}, {"$set": {
        "special_order_id": od["id"], "special_order_number": od.get("number", ""),
        "special_order_item_key": n["key"], "special_order_item_id": n["item_id"]}})
    return {"type": "mko", "id": mko["id"], "number": mko.get("mko_number", ""), "pr_id": pr_id, "product_id": n["product_id"],
            "quantity": n["quantity"], "unit": n["unit"], "created_at": now_iso()}


async def realize_all(od: Dict[str, Any], actor: Dict[str, Any], warehouse_id: str = "") -> Dict[str, Any]:
    """Dipakai auto-procure (kunci harga / retry): realisasikan setiap item yang jalurnya sudah jelas."""
    out: Dict[str, Any] = {"items": [], "errors": []}
    for n in await needs(od):
        fresh = await db.special_orders.find_one({"id": od["id"]}, {"_id": 0})
        try:
            r = await realize(fresh, n["key"], actor, warehouse_id, check_perm=False)
            out["items"].append(r)
        except Exception as exc:  # noqa: BLE001 — satu item gagal tidak menghentikan item lain; error tersimpan per item
            out["errors"].append(f"Item {n['line_no']}: {getattr(exc, 'detail', None) or exc}")
    docs = [i.get("doc") or {} for i in out["items"]]
    po = next((d for d in docs if d.get("type") == "po"), {})
    out.update({"pr_number": next((i.get("pr_number") for i in out["items"] if i.get("pr_number")), ""),
                "po_id": po.get("id", ""), "po_number": po.get("number", "")})
    if out["errors"]:
        await db.special_orders.update_one({"id": od["id"]}, {"$set": {"procurement_error": " · ".join(out["errors"])}})
        if not out["items"]:
            raise FulfillmentError(" · ".join(out["errors"]))
    return out


def summary_note(n: Dict[str, Any]) -> str:
    return f"{n['product_sku']} {n['quantity']:g} {n['unit']} @ {rupiah(n['cost_price'])}"
