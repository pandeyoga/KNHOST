"""Helper functions extracted from routers/sales_orders.py.

Rationale: keep `routers/sales_orders.py` within the ≤800-line router guardrail
(validate_compliance). These are pure orchestration / reservation / lifecycle
helpers — NO routing, NO @router decorators. Behaviour is byte-for-byte
identical to the originals; only their home moved.
"""
from typing import Any, Dict, List
from fastapi import HTTPException
from pymongo import ReturnDocument
from db import db
from dependencies import audit
from core_utils import new_id, now_iso, safe_doc, next_doc_number, strip_cost_fields
from services import product_exclusivity as pexcl
from services.roll_service import (
    reserve_specific_rolls, allocations_from_reserved_rolls, record_reservation_movements,
)
from services.so_status import (
    stage_fields, derive_stage_substatus, SUBSTATUS_LABELS, allowed_action_hint,
)


def normalize_sales_team(raw: List[Any]) -> List[Dict[str, Any]]:
    """F-4c — validasi & normalisasi tim sales (join/group sales).
    Kosong → [] (atribusi insentif default via assigned_sales). Bila diisi:
    Σ split_pct == 100 (toleransi 0.01), tepat 1 PIC, tiap anggota punya sales_id & split_pct > 0."""
    members = []
    for m in raw:
        d = m.model_dump() if hasattr(m, "model_dump") else dict(m)
        sid = (d.get("sales_id") or "").strip()
        if not sid:
            continue
        members.append({
            "sales_id": sid,
            "name": (d.get("name") or "").strip(),
            "role": "pic" if (d.get("role") == "pic") else "co",
            "split_pct": round(float(d.get("split_pct") or 0), 2),
        })
    if not members:
        return []
    from services.customer_service import apply_group_sales_rule
    apply_group_sales_rule(members)   # K-5 — maks 2 orang, split rata otomatis bila kosong
    ids = [m["sales_id"] for m in members]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=400, detail="Anggota sales tim tidak boleh duplikat.")
    if any(m["split_pct"] <= 0 for m in members):
        raise HTTPException(status_code=400, detail="Setiap anggota sales tim harus punya split insentif > 0%.")
    pic_count = sum(1 for m in members if m["role"] == "pic")
    if pic_count != 1:
        raise HTTPException(status_code=400, detail="Sales tim harus punya tepat 1 PIC (penanggung jawab).")
    total = round(sum(m["split_pct"] for m in members), 2)
    if abs(total - 100.0) > 0.01:
        raise HTTPException(status_code=400, detail=f"Total split insentif harus 100% (saat ini {total}%).")
    return members


def norm_backorder(o: Dict[str, Any]) -> Dict[str, Any]:
    """Pastikan field backorder (Sub-fase 1.6) selalu ada di respons SO — jaga
    kontrak FE↔BE konsisten untuk order lama yang dibuat sebelum fitur backorder.
    F4 — fallback: turunkan `stage`+`sub_status` bila belum ada (order legacy)."""
    if not o:
        return o
    o.setdefault("has_backorder", False)
    o.setdefault("backorders", [])
    o.setdefault("has_mixed_lot", False)
    o.setdefault("allocation_policy", {})
    # F4 — stage/sub_status SSOT (derivasi dari status + konteks). Selalu segarkan
    # pada respons agar order legacy/yang belum ter-backfill tetap konsisten.
    if not o.get("stage"):
        o.update(stage_fields(o))
    return o


ROUNDING_CHOICES = ("exact", "exact_whole", "round_up", "round_down", "exact_cut", "take_all")


async def assert_roll_rounding(it_in: Any, actor: Dict[str, Any]) -> Dict[str, Any]:
    """W2-REQ-09 — finalisasi genapkan roll wajib pilihan eksplisit; potong roll hanya berizin."""
    from dependencies import has_permission
    lines = [rl.model_dump() for rl in (it_in.roll_lines or [])]
    rolls = {r["id"]: r for r in await db.inventory_rolls.find(
        {"id": {"$in": [ln["roll_id"] for ln in lines]}},
        {"_id": 0, "id": 1, "length_remaining": 1, "length_reserved": 1}).to_list(len(lines) + 1)}
    final, cut = 0.0, False
    for ln in lines:
        r = rolls.get(ln["roll_id"]) or {}
        free = round(float(r.get("length_remaining") or 0) - float(r.get("length_reserved") or 0), 2)
        take = round(float(ln.get("take_qty") or 0), 2) or free
        cut = cut or take < free - 0.01
        final += take
    final = round(final, 2)
    choice = (it_in.rounding_choice or "").strip()
    target = it_in.target_quantity
    if choice and choice not in ROUNDING_CHOICES:
        raise HTTPException(status_code=422, detail=f"Pilihan genapkan roll tidak dikenal: {choice}")
    if cut:
        if choice != "exact_cut":
            raise HTTPException(status_code=422, detail=(
                "Baris memotong roll — pilih eksplisit 'Potong roll (pas)' sebelum finalisasi."))
        if not await has_permission(actor, "order", "exact_cut"):
            raise HTTPException(status_code=403, detail="Permission ditolak: order.exact_cut (potong roll).")
    if target is not None and target > 0:
        delta = round(final - float(target), 2)
        if not choice:
            raise HTTPException(status_code=422, detail=(
                f"Total roll {final} vs diminta {target} (selisih {delta:+}) — pilih genapkan naik/turun/pas dulu."))
        want = ("exact", "exact_whole", "exact_cut") if abs(delta) <= 0.01 else (
            ("round_up",) if delta > 0 else ("round_down", "take_all"))
        if choice not in want:
            raise HTTPException(status_code=422, detail=(
                f"Pilihan '{choice}' tidak cocok dengan hasil roll (total {final}, diminta {target}, selisih {delta:+})."))
    else:
        target, delta = final, 0.0
    qty = round(float(it_in.base_quantity or it_in.quantity or 0), 2)
    if choice and abs(qty - final) > 0.01:
        raise HTTPException(status_code=422, detail=(
            f"Qty baris ({qty}) harus mengikuti total roll final ({final}) — qty faktur memakai hasil final."))
    return {"target_qty": round(float(target), 2), "final_qty": final, "delta": delta,
            "choice": choice or "explicit_rolls", "roll_count": len(lines), "cut": cut,
            "confirmed_by": actor.get("name", ""), "confirmed_at": now_iso()}


async def reserve_roll_mode_item(
    order_id: str, product_id: str, roll_lines: List[Dict[str, Any]], selling_entity_id: str,
    requested_by: str, warehouses: Dict[str, Any], products: Dict[str, Any],
    policy: Dict[str, Any] = None, makloon_override: bool = False,
) -> Dict[str, Any]:
    """SALES REVAMP V2 — reservasi 1 baris SO mode 'roll' (pilihan roll eksplisit).

    - Roll milik ENTITAS PENJUAL → reserve langsung untuk SO (reserved_ref=sales_order).
    - Roll milik ENTITAS LAIN (1.b) → 2026-10: TIDAK lagi auto-transfer. Qty-nya jadi
      backorder + USULAN sumber (`proposals`) — Admin Sales yang memutuskan pemenuhan.
    Returns: {allocations, reserved_qty, pending_qty, intercompany[], transfer_ids[], proposals[]}.
    """
    norm: List[Dict[str, Any]] = []
    for ln in (roll_lines or []):
        rid = ln.get("roll_id")
        take = round(float(ln.get("take_qty") or 0), 2)
        roll = await db.inventory_rolls.find_one({"id": rid}, {"_id": 0})
        if not roll:
            raise HTTPException(status_code=404, detail=f"Roll {rid} tidak ditemukan.")
        if roll.get("product_id") != product_id:
            raise HTTPException(status_code=400, detail=f"Roll {roll.get('roll_no', rid)} bukan milik produk ini.")
        if roll.get("status") != "available":
            raise HTTPException(status_code=409, detail=f"Roll {roll.get('roll_no', rid)} sudah tidak tersedia.")
        if take <= 0:  # WM-02 — "roll utuh" = panjang BEBAS (sisa − reservasi potong tertunda)
            take = round(float(roll.get("length_remaining", 0) or 0) - float(roll.get("length_reserved") or 0), 2)
        norm.append({"roll_id": rid, "take_qty": take, "owner": roll.get("owner_entity_id")})

    own_lines = [{"roll_id": n["roll_id"], "take_qty": n["take_qty"]} for n in norm if n["owner"] == selling_entity_id]
    cross_by_owner: Dict[str, List[Dict[str, Any]]] = {}
    for n in norm:
        if n["owner"] != selling_entity_id:
            cross_by_owner.setdefault(n["owner"], []).append({"roll_id": n["roll_id"], "take_qty": n["take_qty"]})

    result: Dict[str, Any] = {"allocations": [], "reserved_qty": 0.0, "pending_qty": 0.0,
                              "intercompany": [], "transfer_ids": [], "makloon_overlap_qty": 0.0,
                              "proposals": []}
    # OWN — reservasi langsung untuk SO
    if own_lines:
        # W2-REQ-07 — roll pilihan sales tidak boleh memakan stok yang dicadangkan untuk makloon.
        from services.roll_service import _available_rolls_for_order, makloon_guard, makloon_block_detail
        own_take = round(sum(float(n["take_qty"]) for n in own_lines), 2)
        free_total = sum(float(r["length_remaining"]) for r in
                         await _available_rolls_for_order(product_id, selling_entity_id, order_id))
        guard = await makloon_guard(product_id, selling_entity_id, free_total, own_take, policy,
                                    override=makloon_override, prompt=True)
        if guard["blocked"]:
            raise HTTPException(status_code=409, detail=makloon_block_detail(product_id, guard, own_take))
        result["makloon_overlap_qty"] = guard["overlap"]
        reserved = await reserve_specific_rolls(own_lines, {"type": "sales_order", "id": order_id}, product_id=product_id)
        result["allocations"].extend(allocations_from_reserved_rolls(product_id, reserved, warehouses, status="allocated"))
        await record_reservation_movements(product_id, reserved, order_id, warehouses)
        result["reserved_qty"] += round(sum(float(r.get("length_remaining", 0) or 0) for r in reserved), 2)
    # CROSS (1.b) — 2026-10: roll PT lain = USULAN sumber untuk Admin Sales (tanpa transfer otomatis).
    for source_entity, lines in cross_by_owner.items():
        result["proposals"].append({
            "entity_id": source_entity,
            "qty": round(sum(float(n["take_qty"]) for n in lines), 2),
            "roll_ids": [n["roll_id"] for n in lines]})
    return result


async def so_transition(
    order_id: str, expected_from: List[str], new_status: str,
    actor_name: str, action: str, extra_data: Dict[str, Any] = {}
) -> Dict[str, Any]:
    """Transisi status SO terkontrol + audit. 409 yang MEMANDU bila status tak sesuai."""
    order = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    if not order:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    if order["status"] not in expected_from:
        # Bug poin 14 — pesan 409 yang MEMANDU (sebut tahap saat ini + aksi yang boleh),
        # bukan error mentah. FE memakai ini untuk guard tombol per-stage.
        cur_stage, cur_subs = derive_stage_substatus(order)
        sub_label = ", ".join(SUBSTATUS_LABELS.get(s, s) for s in cur_subs) if cur_subs else ""
        hint = allowed_action_hint(order["status"])
        raise HTTPException(status_code=409, detail={
            "code": "INVALID_TRANSITION",
            "message": (
                f"Pesanan ada di tahap '{cur_stage}'"
                + (f" ({sub_label})" if sub_label else "")
                + f" sehingga aksi '{action}' belum bisa dijalankan. {hint}"
            ),
            "current_status": order["status"],
            "current_stage": cur_stage,
            "current_sub_status": cur_subs,
            "attempted_action": action,
            "allowed_from": expected_from,
        })
    update_data = {"status": new_status, "updated_at": now_iso(), **extra_data}
    # F4 — sinkronkan stage + sub_status (turunan dari status final + konteks).
    update_data.update(stage_fields({**order, **update_data}))
    # INV-ATOMIC-01 — CAS: tulisan akhir berprasyarat status yang tadi dibaca, dan sekaligus
    # mencabut `saga_lock` bila endpoint pemanggil mengklaimnya (T-01 Opsi B).
    order = await db.sales_orders.find_one_and_update(
        {"id": order_id, "status": {"$in": expected_from}},
        {"$set": update_data, "$unset": {"saga_lock": ""}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    if not order:
        raise HTTPException(status_code=409, detail={
            "code": "INVALID_TRANSITION",
            "message": f"Pesanan berubah status oleh proses lain sebelum aksi '{action}' selesai. Muat ulang layar.",
            "attempted_action": action, "allowed_from": expected_from})
    await audit(actor_name, action, "sales_order", order_id, {"status": new_status})
    return order


async def compute_frequent_products(customer_id: str, limit: int, actor: Dict[str, Any]) -> List[Dict[str, Any]]:
    """EPIC5 — "Sering dibeli customer ini" (reorder).

    Agregasi item dari order historis customer → produk paling sering dipesan
    (frekuensi order + total qty), digabung data produk terkini (harga, stok,
    gambar) agar bisa langsung di-reorder dari POS. Logika dipindah dari
    routers/sales_orders.py agar router tetap ≤800 baris (guardrail).
    """
    if not customer_id:
        return []
    orders = await db.sales_orders.find(
        {"customer_id": customer_id},
        {"_id": 0, "items": 1, "created_at": 1},
    ).to_list(500)
    stats: Dict[str, Dict[str, Any]] = {}
    for o in orders:
        for it in (o.get("items") or []):
            pid = it.get("product_id")
            if not pid:
                continue
            s = stats.setdefault(pid, {"product_id": pid, "order_count": 0, "total_qty": 0.0,
                                       "last_unit": it.get("unit"), "last_ordered": o.get("created_at")})
            s["order_count"] += 1
            s["total_qty"] += float(it.get("base_quantity", it.get("quantity", 0)) or 0)
            if str(o.get("created_at") or "") > str(s["last_ordered"] or ""):
                s["last_ordered"] = o.get("created_at")
                s["last_unit"] = it.get("unit")
    if not stats:
        return []
    ranked = sorted(stats.values(), key=lambda s: (s["order_count"], s["total_qty"]), reverse=True)[:max(1, min(limit, 24))]
    pids = [s["product_id"] for s in ranked]
    prods = {p["id"]: p for p in await db.products.find({"id": {"$in": pids}}, {"_id": 0}).to_list(100)}
    out: List[Dict[str, Any]] = []
    for s in ranked:
        p = prods.get(s["product_id"])
        if not p or p.get("status") == "inactive":
            continue
        # PS-20 — jangan bocorkan produk eksklusif milik sales lain di daftar reorder.
        if not pexcl.can_view(actor, p):
            continue
        out.append({
            **p,
            "reorder_count": s["order_count"],
            "reorder_total_qty": round(s["total_qty"], 2),
            "reorder_last_unit": s["last_unit"],
        })
    return strip_cost_fields([safe_doc(x) for x in out], (actor or {}).get("role"))
