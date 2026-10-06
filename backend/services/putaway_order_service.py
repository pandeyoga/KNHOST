"""FASE R2 — PUTAWAY ORDER (PA): dokumen pemindahan roll dari gedung transit ke
gedung penyimpanan, dengan enforcement `storage_rules` + BTG (Bukti Terima Gudang).

SSOT: perpindahan antar-gedung mengubah `roll.warehouse_id` lalu `rebuild_balance`
kedua sisi (balance = proyeksi dari rolls, tidak pernah $inc). Kepemilikan TIDAK
berubah (bukan interco). Journey: putaway_assigned → putaway_in_transit → stored
(atau gate_exception untuk item yang tak tervalidasi saat tiba).
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso, next_doc_number, safe_doc
from services import warehouse_profile_service as whp
from services.rfid_print_service import set_journey


async def putaway_block_reason(r: Dict[str, Any]) -> Optional[str]:
    """G3 D4-WMS-04 — resolver kelayakan putaway bersama (health, suggest, create). None = siap."""
    if r.get("status") != "available":
        return f"status_{r.get('status') or 'unknown'}"
    if r.get("active_movement"):
        return "active_movement"
    if float(r.get("length_reserved") or 0) > 0:
        return "reserved"
    if (await identity_issue(r))[0] is not None:
        return "tag_identity"
    return None


async def _rolls_ready(warehouse_id: str, scope_ids: List[str], limit: int = 2000) -> List[Dict[str, Any]]:
    """Roll di gudang transit yang siap putaway: tag_verified + routing store."""
    rolls = await db.inventory_rolls.find({
        "warehouse_id": warehouse_id, "owner_entity_id": {"$in": scope_ids},
        "length_remaining": {"$gt": 0},
        "journey.stage": "tag_verified",
        "journey.routing": {"$ne": "cross_dock"},
        "status": "available", "active_movement": None,  # AX-08/WM-05
        "length_reserved": {"$not": {"$gt": 0}},
    }, {"_id": 0}).to_list(limit)
    rolls = [r for r in rolls if await putaway_block_reason(r) is None]  # G3 D4-TAG-01 / D4-WMS-04
    pids = list({r["product_id"] for r in rolls})
    prods = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": pids}}, {"_id": 0, "id": 1, "sku": 1, "name": 1, "category": 1}).to_list(3000)}
    for r in rolls:
        p = prods.get(r["product_id"], {})
        r["sku"], r["product_name"], r["category"] = p.get("sku", ""), p.get("name", ""), p.get("category", "")
    return rolls


async def suggest(warehouse_from: str, scope_ids: List[str]) -> Dict[str, Any]:
    """Kelompokkan roll siap-putaway per (owner, kategori) + kandidat gudang tujuan
    berdasarkan roles=storage + storage_rules match (site sama diprioritaskan)."""
    src = await db.warehouses.find_one({"id": warehouse_from}, {"_id": 0})
    if not src:
        raise HTTPException(status_code=404, detail="Gudang asal tidak ditemukan")
    rolls = await _rolls_ready(warehouse_from, scope_ids)
    storages = await db.warehouses.find(
        {"active": {"$ne": False}, "roles": "storage", "id": {"$ne": warehouse_from}},
        {"_id": 0}).to_list(200)
    groups: Dict[str, Dict[str, Any]] = {}
    for r in rolls:
        unit = r.get("unit", "meter")
        # G3 D4-PA-03 — satuan masuk kunci grup: meter dan kg tidak pernah dijumlahkan jadi satu angka
        key = f"{r.get('owner_entity_id')}|{r.get('category') or '—'}|{(r.get('grade') or 'A').upper()}|{unit}"
        g = groups.setdefault(key, {
            "owner_entity_id": r.get("owner_entity_id"), "category": r.get("category") or "",
            "grade": (r.get("grade") or "A").upper(),
            "rolls": [], "qty": 0.0, "unit": unit, "candidates": None})
        g["rolls"].append({k: r.get(k) for k in (
            "id", "roll_no", "sku", "product_name", "category", "grade",
            "length_remaining", "unit", "lot", "rfid_tag_id")})
        g["qty"] += float(r.get("length_remaining") or 0)
    for g in groups.values():
        cands = []
        for wh in storages:
            check = whp.check_storage_rules(wh, g["category"], g["grade"])
            if check["ok"]:
                cands.append({"warehouse_id": wh["id"], "warehouse_name": wh.get("name", ""),
                              "site_id": wh.get("site_id", ""),
                              "same_site": wh.get("site_id") and wh.get("site_id") == src.get("site_id"),
                              "rules_mode": (wh.get("storage_rules") or {}).get("mode", "none")})
        cands.sort(key=lambda c: (not c["same_site"], c["rules_mode"] == "none"))
        g["candidates"] = cands
        g["qty"] = round(g["qty"], 2)
    return {"warehouse_from": {"id": src["id"], "name": src.get("name", "")},
            "ready_count": len(rolls), "groups": list(groups.values())}


PA_ELIGIBLE_STATUS = "available"  # AX-08 — QC hold/quarantine/reserved tidak boleh diputaway


async def identity_issue(r: Dict[str, Any]):
    """G3 D4-TAG-01 — kesiapan identitas terikat ke tag AKTIF saat ini + bukti verifikasi tag itu.
    Tag lama yang di-retire / tag baru yang belum dicetak-diverifikasi tidak lolos."""
    tid = r.get("rfid_tag_id")
    if not tid:
        return "tidak punya tag RFID (tag dihapus/diganti) — cetak & verifikasi tag baru", None
    tag = await db.rfid_tags.find_one({"id": tid}, {"_id": 0})
    if not tag or tag.get("status") != "active":
        return f"tag RFID berstatus {(tag or {}).get('status') or 'hilang'} — belum aktif/terverifikasi", None
    if tag.get("roll_id") != r.get("id") or not tag.get("epc"):
        return "tag RFID tidak tertaut benar ke roll ini", None
    j = r.get("journey") or {}
    if j.get("verified_tag_id"):
        ok = j["verified_tag_id"] == tid
    else:  # data lama tanpa verified_tag_id: tag tidak boleh lahir sesudah verifikasi terakhir
        ok = not tag.get("created_at") or str(tag["created_at"]) <= str(j.get("updated_at") or "")
    if not ok:
        return "tag RFID saat ini belum diverifikasi (bukti verifikasi milik tag lama)", None
    return None, tag


async def _release_claims(roll_ids: List[str], order_id: str) -> None:
    from services.roll_service import rebuild_balance
    segs = {(r["product_id"], r["warehouse_id"], r.get("owner_entity_id")) async for r in db.inventory_rolls.find(
        {"id": {"$in": roll_ids}, "active_movement.id": order_id},
        {"_id": 0, "product_id": 1, "warehouse_id": 1, "owner_entity_id": 1})}
    await db.inventory_rolls.update_many(
        {"id": {"$in": roll_ids}, "active_movement.id": order_id, "status": PA_ELIGIBLE_STATUS},
        {"$unset": {"active_movement": ""}})
    for pid, wid, own in segs:
        await rebuild_balance(pid, wid, own)


async def create_order(warehouse_from: str, warehouse_to: str, roll_ids: List[str],
                       scope_ids: List[str], actor_name: str) -> Dict[str, Any]:
    if not roll_ids:
        raise HTTPException(status_code=400, detail="Pilih minimal satu roll")
    if warehouse_from == warehouse_to:
        raise HTTPException(status_code=400, detail="Gudang asal dan tujuan sama")
    roll_ids = list(dict.fromkeys(roll_ids))
    wh_to = await db.warehouses.find_one({"id": warehouse_to}, {"_id": 0})
    wh_from = await db.warehouses.find_one({"id": warehouse_from}, {"_id": 0})
    if not wh_to or not wh_from:
        raise HTTPException(status_code=404, detail="Gudang tidak ditemukan")
    rolls = await db.inventory_rolls.find(
        {"id": {"$in": roll_ids}, "warehouse_id": warehouse_from,
         "owner_entity_id": {"$in": scope_ids}}, {"_id": 0}).to_list(len(roll_ids) + 5)
    if len(rolls) != len(roll_ids):
        raise HTTPException(status_code=400,
                            detail="Sebagian roll tidak ditemukan di gudang asal / di luar entitas")
    owners = {r.get("owner_entity_id") for r in rolls}
    if len(owners) > 1:
        raise HTTPException(status_code=400, detail="Satu PA hanya untuk satu pemilik barang")
    pids = list({r["product_id"] for r in rolls})
    prods = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": pids}}, {"_id": 0, "id": 1, "sku": 1, "name": 1, "category": 1}).to_list(3000)}
    items, violations = [], []
    for r in rolls:
        stage = (r.get("journey") or {}).get("stage")
        if stage not in ("tag_verified",):
            violations.append(f"Roll {r.get('roll_no')} belum terverifikasi (stage: {stage or '—'})")
            continue
        # AX-08 — tag terverifikasi BUKAN izin gerak: status kualitas/reservasi roll juga wajib bebas.
        if r.get("status") != PA_ELIGIBLE_STATUS:
            violations.append(f"Roll {r.get('roll_no')} berstatus {r.get('status')} — putaway hanya "
                              "untuk roll available (lolos QC, tidak dipesan)")
            continue
        if float(r.get("length_reserved") or 0) > 0:  # WM-02 — ada reservasi potong tertunda
            violations.append(f"Roll {r.get('roll_no')} punya reservasi potong yang belum dikonfirmasi")
            continue
        if float(r.get("length_remaining") or 0) <= 0:
            violations.append(f"Roll {r.get('roll_no')} panjangnya 0")
            continue
        if (r.get("active_movement") or {}).get("id"):
            violations.append(f"Roll {r.get('roll_no')} sedang dalam perpindahan "
                              f"{r['active_movement'].get('number') or r['active_movement']['id']}")
            continue
        p = prods.get(r["product_id"], {})
        check = whp.check_storage_rules(wh_to, p.get("category", ""), r.get("grade", "A"))
        if not check["ok"]:
            violations.append(check["reason"])
            continue
        why, tag = await identity_issue(r)
        if why:
            violations.append(f"Roll {r.get('roll_no')}: {why}")
            continue
        items.append({
            "roll_id": r["id"], "roll_no": r.get("roll_no", ""), "epc": tag.get("epc", ""),
            "sku": p.get("sku", ""), "product_name": p.get("name", ""),
            "category": p.get("category", ""), "grade": r.get("grade", ""),
            "product_id": r["product_id"], "lot": r.get("lot", ""),
            "qty": float(r.get("length_remaining") or 0), "unit": r.get("unit", "meter"),
            "status": "pending",
        })
    if violations:
        raise HTTPException(status_code=400, detail=" | ".join(violations[:5]))
    order_id = new_id("pa")
    pa_number = await next_doc_number("putaway_orders", "pa_number", "PA")
    # WM-05 — klaim kepemilikan perpindahan PER ROLL (atomik, all-or-none) sebelum PA lahir.
    claimed: List[str] = []
    for it in items:
        res = await db.inventory_rolls.update_one(
            {"id": it["roll_id"], "warehouse_id": warehouse_from, "status": PA_ELIGIBLE_STATUS,
             "journey.stage": "tag_verified", "length_remaining": {"$gt": 0}, "active_movement": None,
             "length_reserved": {"$not": {"$gt": 0}}},
            {"$set": {"active_movement": {"type": "putaway", "id": order_id, "number": pa_number,
                                          "claimed_at": now_iso()}}})
        if res.modified_count != 1:
            await _release_claims(claimed, order_id)
            raise HTTPException(status_code=409, detail=(
                f"Roll {it['roll_no']} baru saja diambil proses lain (PA/reservasi/QC). Muat ulang layar."))
        claimed.append(it["roll_id"])
    order = {
        "id": order_id,
        "pa_number": pa_number,
        "from_warehouse_id": warehouse_from, "from_warehouse_name": wh_from.get("name", ""),
        "to_warehouse_id": warehouse_to, "to_warehouse_name": wh_to.get("name", ""),
        "owner_entity_id": list(owners)[0],
        "items": items, "item_count": len(items),
        "total_qty": round(sum(i["qty"] for i in items), 2),
        # G3 D4-PA-03 — total per satuan (meter/kg/yard tidak dijumlahkan jadi satu label)
        "qty_by_unit": {u: round(sum(i["qty"] for i in items if (i.get("unit") or "meter") == u), 2)
                        for u in {(i.get("unit") or "meter") for i in items}},
        "mixed_units": len({(i.get("unit") or "meter") for i in items}) > 1,
        "status": "open", "btg_number": None,
        "created_at": now_iso(), "created_by": actor_name,
        "dispatched_at": None, "confirmed_at": None, "confirmed_by": None,
    }
    try:
        await db.putaway_orders.insert_one(dict(order))
    except Exception:
        await _release_claims(claimed, order_id)
        raise
    from services.roll_service import rebuild_balance
    for pid in {i["product_id"] for i in items}:  # G3 D4-PA-01 — roll diklaim PA keluar dari ATP
        await rebuild_balance(pid, warehouse_from, order["owner_entity_id"])
    await set_journey([i["roll_id"] for i in items], "putaway_assigned", {"putaway_order_id": order["id"]})
    return safe_doc(order)


async def list_orders(scope_ids: List[str], warehouse_id: Optional[str],
                      status: Optional[str], limit: int = 100) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"owner_entity_id": {"$in": scope_ids}}
    if warehouse_id:
        q["$or"] = [{"from_warehouse_id": warehouse_id}, {"to_warehouse_id": warehouse_id}]
    if status:
        q["status"] = status
    orders = await db.putaway_orders.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return [safe_doc(o) for o in orders]


async def _get(order_id: str, scope_ids: List[str]) -> Dict[str, Any]:
    order = await db.putaway_orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Putaway Order tidak ditemukan")
    if order.get("owner_entity_id") not in scope_ids:
        raise HTTPException(status_code=403, detail="PA di luar entitas Anda")
    return order


async def dispatch(order_id: str, scope_ids: List[str]) -> Dict[str, Any]:
    """WM-04 — roll pindah bucket available → in_transit_transfer (ATP asal turun, owned tetap)."""
    from services.roll_service import rebuild_balance
    from services import atomic_claim as _saga
    order = await _get(order_id, scope_ids)
    if order["status"] != "open":
        raise HTTPException(status_code=400, detail=f"PA berstatus {order['status']}")
    await _saga.claim("putaway_orders", order_id, "putaway_dispatch", precondition={"status": "open"})
    moved: List[Dict[str, Any]] = []
    for it in order["items"]:
        # G3 D4-TAG-01 — identitas diperiksa ulang sebelum efek (tag bisa diganti sesudah PA dibuat)
        roll = await db.inventory_rolls.find_one({"id": it["roll_id"]}, {"_id": 0}) or {}
        why, tag = await identity_issue(roll)
        bad_identity = bool(why) or (tag or {}).get("epc", "").upper() != (it.get("epc") or "").upper()
        # G3 D4-PA-01 — CAS juga menolak roll yang punya reservasi panjang (potong) live
        res = None if bad_identity else await db.inventory_rolls.update_one(
            {"id": it["roll_id"], "active_movement.id": order_id, "status": PA_ELIGIBLE_STATUS,
             "warehouse_id": order["from_warehouse_id"], "length_reserved": {"$not": {"$gt": 0}}},
            {"$set": {"status": "in_transit_transfer", "updated_at": now_iso()}})
        if res is None or res.modified_count != 1:
            for m in moved:  # kompensasi: tidak ada PA setengah terkirim
                await db.inventory_rolls.update_one(
                    {"id": m["roll_id"], "active_movement.id": order_id, "status": "in_transit_transfer"},
                    {"$set": {"status": PA_ELIGIBLE_STATUS}})
            await _saga.release("putaway_orders", order_id)
            raise HTTPException(status_code=409, detail=(
                f"Roll {it['roll_no']} " + (f"identitasnya berubah: {why or 'EPC berbeda dari PA'}. " if bad_identity
                                            else "tidak lagi available untuk PA ini (dipesan/QC/berpindah). ")
                + "Keluarkan roll itu atau buat PA baru."))
        moved.append(it)
    for pid in {i["product_id"] for i in order["items"]}:
        await rebuild_balance(pid, order["from_warehouse_id"], order["owner_entity_id"])
    await db.putaway_orders.update_one({"id": order_id}, _saga.finish_set({
        "status": "in_transit", "dispatched_at": now_iso(), "updated_at": now_iso()}))
    await set_journey([i["roll_id"] for i in order["items"]], "putaway_in_transit")
    return await _get(order_id, scope_ids)


async def _land_items(order: Dict[str, Any], items: List[Dict[str, Any]], actor_name: str,
                      reason: str) -> List[Dict[str, Any]]:
    """Satu jalur posting perpindahan (arrival normal & exception — WM-09): CAS roll milik PA ini,
    pindah gudang, tulis pasangan mutasi out/in, rebuild kedua lokasi. Hasil = item yang benar-benar pindah."""
    from services.roll_service import rebuild_balance
    now = now_iso()
    landed, movements, segs = [], [], set()
    for item in items:
        res = await db.inventory_rolls.update_one(
            {"id": item["roll_id"], "active_movement.id": order["id"],
             "warehouse_id": order["from_warehouse_id"],
             "status": {"$in": [PA_ELIGIBLE_STATUS, "in_transit_transfer"]}},
            {"$set": {"warehouse_id": order["to_warehouse_id"], "bin_id": None,
                      "status": PA_ELIGIBLE_STATUS, "updated_at": now, "last_pa_landed": order["id"]},
             "$unset": {"active_movement": ""}})
        if res.modified_count != 1:
            # G3 D4-PA-02 — percobaan sebelumnya sudah memindah roll ini untuk PA yang SAMA tapi mati
            # sebelum tag/mutasi/saldo → ADOPSI efeknya dan lanjutkan langkah sisanya (idempoten).
            if not await db.inventory_rolls.find_one({"id": item["roll_id"], "last_pa_landed": order["id"],
                                                      "warehouse_id": order["to_warehouse_id"]}, {"_id": 1}):
                item["status"] = "exception"
                item["exception_reason"] = "Roll tidak lagi milik PA ini / status berubah"
                continue
        await db.rfid_tags.update_one({"roll_id": item["roll_id"], "status": "active"},
                                      {"$set": {"warehouse_id": order["to_warehouse_id"]}})
        item["status"] = "arrived"
        item.pop("exception_reason", None)
        landed.append(item)
        for wh, mtype in ((order["from_warehouse_id"], "putaway_transfer_out"),
                          (order["to_warehouse_id"], "putaway_transfer_in")):
            movements.append({
                "id": f"mov_pa_{order['id']}_{item['roll_id']}_{mtype[-3:].strip('_')}",
                "product_id": item["product_id"], "warehouse_id": wh,
                "owner_entity_id": order["owner_entity_id"], "movement_type": mtype,
                "quantity": item["qty"] if mtype.endswith("_in") else -item["qty"],
                "unit": item["unit"], "lot": item.get("lot", ""), "roll_id": item["roll_id"],
                "qty_rolls": 1, "source_document": order["pa_number"], "reference_id": order["id"],
                "reason": reason, "created_by": actor_name, "timestamp": now,
            })
        segs.add((item["product_id"], order["from_warehouse_id"]))
        segs.add((item["product_id"], order["to_warehouse_id"]))
    for mv in movements:   # id deterministik per (PA, roll, arah) → retry tidak menggandakan mutasi
        await db.inventory_movements.update_one({"id": mv["id"]}, {"$setOnInsert": mv}, upsert=True)
    for pid, wid in segs:
        await rebuild_balance(pid, wid, order["owner_entity_id"])
    if landed:
        await set_journey([i["roll_id"] for i in landed], "stored", {"putaway_order_id": order["id"]})
    return landed


MIN_OVERRIDE_REASON = 10


async def confirm_arrival(order_id: str, scanned_epcs: Optional[List[str]],
                          scope_ids: List[str], actor_name: str,
                          manual_all: bool = False, reason: str = "") -> Dict[str, Any]:
    """Validasi tiba di gate-in gudang tujuan. WM-03: `scanned_epcs=[]` = NOL roll tiba;
    tanpa hasil scan hanya boleh lewat override manual ber-alasan (`manual_all`)."""
    order = await _get(order_id, scope_ids)
    if order["status"] not in ("open", "in_transit"):
        raise HTTPException(status_code=400, detail=f"PA berstatus {order['status']}")
    why = (reason or "").strip()
    if manual_all:
        if len(why) < MIN_OVERRIDE_REASON:
            raise HTTPException(status_code=400, detail=(
                f"Konfirmasi manual tanpa scan wajib beralasan (minimal {MIN_OVERRIDE_REASON} huruf)."))
    elif scanned_epcs is None:
        raise HTTPException(status_code=400, detail=(
            "Kirim hasil scan EPC, atau pilih konfirmasi manual (semua tiba) dengan alasan."))
    # INV-ATOMIC-01 (T-01 Opsi B) — klaim PA sebelum roll/tag/mutasi ditulis.
    from services import atomic_claim as _saga
    await _saga.claim("putaway_orders", order_id, "putaway_confirm_arrival",
                      precondition={"status": {"$in": ["open", "in_transit"]}}, actor=actor_name)
    try:
        return await _confirm_arrival_claimed(order, order_id, scanned_epcs, scope_ids, actor_name,
                                              manual_all, why, _saga)
    except BaseException:
        # G3 D4-PA-02 — gagal di tengah: kunci dilepas supaya retry lewat fitur asli bisa MELANJUTKAN
        # (roll yang sudah dipindah untuk PA ini diadopsi oleh _land_items; mutasi ber-id deterministik).
        await _saga.release("putaway_orders", order_id)
        raise


async def _confirm_arrival_claimed(order, order_id, scanned_epcs, scope_ids, actor_name, manual_all, why, _saga):
    scanned = {e.strip().upper() for e in (scanned_epcs or []) if e and e.strip()}
    candidates, exceptions = [], []
    for item in order["items"]:
        if manual_all or (item.get("epc") and item["epc"].upper() in scanned):
            candidates.append(item)
        else:
            item["status"] = "exception"
            item["exception_reason"] = "EPC tidak terbaca saat konfirmasi tiba"
            exceptions.append(item)
    arrived = await _land_items(order, candidates, actor_name,
                                f"manual: {why}" if manual_all else "gate-in scan")
    exceptions += [i for i in candidates if i["status"] == "exception"]
    if exceptions:
        await set_journey([i["roll_id"] for i in exceptions], "gate_exception",
                          {"exception_reason": "EPC tidak terbaca / roll berubah saat konfirmasi tiba",
                           "putaway_order_id": order_id})
    now = now_iso()
    btg = await next_doc_number("putaway_orders", "btg_number", "BTG") if arrived else None
    status = "completed" if not exceptions else ("completed_with_exception" if arrived else "exception")
    upd: Dict[str, Any] = {
        "items": order["items"], "status": status, "btg_number": btg,
        "arrived_count": len(arrived), "exception_count": len(exceptions),
        "confirmed_at": now, "confirmed_by": actor_name, "updated_at": now}
    if manual_all:
        upd["manual_override"] = {"by": actor_name, "reason": why, "at": now}
    await db.putaway_orders.update_one({"id": order_id}, _saga.finish_set(upd))
    return await _get(order_id, scope_ids)


async def resolve_exception(order_id: str, roll_ids: List[str], action: str,
                            scope_ids: List[str], actor_name: str, reason: str = "") -> Dict[str, Any]:
    """Checker (handheld scan ulang di ERP): `accept` = barang ternyata sah → pindahkan (mutasi
    ditulis lewat jalur yang sama dengan arrival); `return_transit` = kembali siap-putaway di asal."""
    from services.roll_service import rebuild_balance
    order = await _get(order_id, scope_ids)
    if action not in ("accept", "return_transit"):
        raise HTTPException(status_code=400, detail="Aksi harus 'accept' atau 'return_transit'")
    target = [i for i in order["items"] if i["status"] == "exception" and i["roll_id"] in set(roll_ids)]
    if not target:
        raise HTTPException(status_code=404, detail="Tidak ada item exception yang cocok")
    # INV-ATOMIC-01 — klaim perintah putaway sebelum roll/tag/jejak/balance ditulis.
    from services import atomic_claim as _saga
    await _saga.claim("putaway_orders", order_id, "putaway_resolve_exception", actor=actor_name)
    now = now_iso()
    why = (reason or "").strip() or f"exception {action} oleh {actor_name}"
    if action == "accept":
        await _land_items(order, target, actor_name, f"exception accept: {why}")
        for i in target:
            if i["status"] == "arrived":
                i["resolved_by"], i["resolved_at"] = actor_name, now
    else:  # return_transit
        segs = set()
        for item in target:
            res = await db.inventory_rolls.update_one(
                {"id": item["roll_id"], "active_movement.id": order_id,
                 "status": {"$in": [PA_ELIGIBLE_STATUS, "in_transit_transfer"]}},
                {"$set": {"status": PA_ELIGIBLE_STATUS, "updated_at": now},
                 "$unset": {"active_movement": ""}})
            if res.modified_count == 1:
                item["status"] = "returned_transit"
                item["resolved_by"], item["resolved_at"] = actor_name, now
                segs.add((item["product_id"], order["from_warehouse_id"]))
                await set_journey([item["roll_id"]], "tag_verified", {"exception_resolved_by": actor_name})
        for pid, wid in segs:
            await rebuild_balance(pid, wid, order["owner_entity_id"])
    still_exc = [i for i in order["items"] if i["status"] == "exception"]
    arrived_any = any(i["status"] == "arrived" for i in order["items"])
    status = "completed" if not still_exc else "completed_with_exception"
    upd: Dict[str, Any] = {"items": order["items"], "status": status,
                           "arrived_count": sum(1 for i in order["items"] if i["status"] == "arrived"),
                           "exception_count": len(still_exc), "updated_at": now}
    if arrived_any and not order.get("btg_number"):
        upd["btg_number"] = await next_doc_number("putaway_orders", "btg_number", "BTG")
    await db.putaway_orders.update_one({"id": order_id}, _saga.finish_set(upd))
    return await _get(order_id, scope_ids)
