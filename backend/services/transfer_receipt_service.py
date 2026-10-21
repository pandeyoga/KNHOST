"""P03 (IMP-26/27) + sisa P02 — transfer terkait SO, penerimaan AKTUAL per roll, exception, cek ulang aturan tujuan.

- Roll berkomitmen SO dipindah tanpa reservasi kedua (`transfer_ref`), komitmen tetap selama perjalanan.
- Penerimaan per roll (CAS, idempoten): hanya roll yang benar-benar diterima menjadi stok fisik tujuan.
- Aturan gudang tujuan dievaluasi ULANG saat terima; pelanggaran = exception terkontrol (supervisor + alasan → hold).
- Exception (hilang, roll salah, rusak, aturan) ber-PIC/alasan; "Selesai" hanya bila tidak ada roll di perjalanan.
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso
from services import placement_rules as pr
from services.roll_service import (held_cas, owned_by_transfer, rebuild_balance, so_still_open,
                                   transfer_held_rolls)

DONE = {"completed", "rejected", "cancelled"}
EXC_KINDS = {"missing", "wrong_roll", "damaged", "rule_violation", "other"}


def _roll_ids(transfer: Dict[str, Any]) -> List[str]:
    return [x["roll_id"] for it in transfer.get("items") or [] for x in it.get("rolls") or [] if x.get("roll_id")]


SO_HELD = ("reserved", "committed")   # roll berkomitmen ke SO (sebelum / sesudah dikonfirmasi)
# Hanya SO yang tugas gudangnya BELUM mulai diambil: alokasi & tugas "created" ikut pindah ke gudang tujuan.
SO_TRANSFERABLE = {"reserved", "waiting_approval", "approved", "confirmed", "waiting_stock"}

def _reason(text: str, label: str = "Alasan") -> str:
    t = (text or "").strip()
    if len(t) < 5:
        raise HTTPException(status_code=400, detail=f"{label} wajib diisi (minimal 5 karakter).")
    return t


# ─── Transfer terkait SO (IMP-26) ──────────────────────────────────────────────
async def so_options(source_warehouse_id: str, allowed: List[str]) -> List[Dict[str, Any]]:
    """SO yang punya roll berkomitmen (reserved) di gudang asal."""
    # Cek UI UAT v3 (S10) — roll SO terkonfirmasi berstatus "committed"; dulu hanya "reserved" → transfer pemenuhan SO tak pernah bisa dipakai.
    q: Dict[str, Any] = {"warehouse_id": source_warehouse_id, "status": {"$in": list(SO_HELD)},
                         "reserved_ref.type": "sales_order"}
    if allowed:
        q["owner_entity_id"] = {"$in": allowed}
    rows = await db.inventory_rolls.aggregate([
        {"$match": q}, {"$group": {"_id": "$reserved_ref.id", "rolls": {"$sum": 1}}}]).to_list(500)
    out = []
    for r in rows:
        so = await db.sales_orders.find_one({"id": r["_id"]}, {"_id": 0, "id": 1, "number": 1, "customer_name": 1,
                                                               "status": 1, "entity_id": 1})
        if so and so.get("status") in SO_TRANSFERABLE:
            out.append({**so, "rolls_here": r["rolls"]})
    return sorted(out, key=lambda s: s.get("number") or "")


async def so_rolls(so_id: str, source_warehouse_id: str) -> List[Dict[str, Any]]:
    rows = await db.inventory_rolls.find(
        {"reserved_ref.id": so_id, "warehouse_id": source_warehouse_id, "status": {"$in": list(SO_HELD)}},
        {"_id": 0}).to_list(2000)
    prods = {p["id"]: p for p in await db.products.find({"id": {"$in": list({r["product_id"] for r in rows})}},
                                                        {"_id": 0, "id": 1, "sku": 1, "name": 1, "base_unit": 1}).to_list(500)}
    out = []
    for r in rows:
        busy = await _active_transfer_of(r)
        p = prods.get(r["product_id"], {})
        out.append({"roll_id": r["id"], "roll_no": r.get("roll_no"), "lot": r.get("lot"), "product_id": r["product_id"],
                    "sku": p.get("sku", ""), "product_name": p.get("name", ""), "unit": r.get("unit") or p.get("base_unit"),
                    "length": float(r.get("length_remaining") or 0), "grade": r.get("grade", "A"),
                    "in_transfer": busy.get("code") if busy else ""})
    return out


async def _active_transfer_of(roll: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tid = (roll.get("transfer_ref") or {}).get("id")
    if not tid:
        return None
    return await db.warehouse_transfers.find_one({"id": tid, "status": {"$nin": list(DONE)}}, {"_id": 0, "id": 1, "code": 1})


async def validate_so_link(so_id: str, owner: str) -> Dict[str, Any]:
    so = await db.sales_orders.find_one({"id": so_id}, {"_id": 0, "id": 1, "number": 1, "status": 1, "entity_id": 1,
                                                        "customer_name": 1})
    if not so:
        raise HTTPException(status_code=404, detail="SO yang ditautkan tidak ditemukan.")
    if not await so_still_open(so_id):
        raise HTTPException(status_code=400, detail=f"SO {so.get('number')} sudah {so.get('status')} — tidak bisa dipenuhi lewat transfer.")
    if owner and so.get("entity_id") and so["entity_id"] != owner:
        raise HTTPException(status_code=400, detail=(
            f"Roll milik badan usaha lain dari SO {so.get('number')}. Pindah fisik tidak menggantikan jual-beli "
            "internal — buat transaksi antar-PT dulu."))
    return so


async def attach_committed_rolls(transfer_id: str, so_id: str, roll_ids: List[str], source_wh: str,
                                 product_id: str) -> List[Dict[str, Any]]:
    """Roll reserved untuk SO → ditandai milik transfer TANPA melepas/mengulang reservasi (CAS)."""
    out: List[Dict[str, Any]] = []
    so = await db.sales_orders.find_one({"id": so_id}, {"_id": 0, "number": 1, "status": 1}) or {}
    if so.get("status") not in SO_TRANSFERABLE:
        raise HTTPException(status_code=409, detail=(
            f"SO {so.get('number', '')} sudah mulai diambil gudang — kirim dari gudang asal atau batalkan pengambilan dulu."))
    rows = await db.inventory_rolls.find({"id": {"$in": roll_ids}}, {"_id": 0}).to_list(len(roll_ids))
    by_id = {r["id"]: r for r in rows}
    try:
        for rid in roll_ids:
            r = by_id.get(rid)
            if not r or r.get("product_id") != product_id:
                raise HTTPException(status_code=409, detail="Sebagian roll tidak ditemukan untuk produk ini — muat ulang.")
            if r.get("status") not in SO_HELD or (r.get("reserved_ref") or {}).get("id") != so_id:
                raise HTTPException(status_code=409, detail=f"Roll {r.get('roll_no')} tidak (lagi) berkomitmen ke SO ini.")
            if r.get("warehouse_id") != source_wh:
                raise HTTPException(status_code=400, detail=f"Roll {r.get('roll_no')} tidak berada di gudang asal.")
            busy = await _active_transfer_of(r)
            if busy:
                raise HTTPException(status_code=409, detail=f"Roll {r.get('roll_no')} sudah ada di transfer {busy.get('code')}.")
            res = await db.inventory_rolls.update_one(
                {**held_cas(r), "transfer_ref": r.get("transfer_ref"), "active_movement": None},
                {"$set": {"transfer_ref": {"type": "wh_transfer", "id": transfer_id, "so_id": so_id}, "updated_at": now_iso()}})
            if not res.matched_count:
                raise HTTPException(status_code=409, detail=f"Roll {r.get('roll_no')} baru saja berubah — muat ulang.")
            out.append(r)
    except HTTPException:
        await db.inventory_rolls.update_many({"transfer_ref.id": transfer_id, "id": {"$in": [x["id"] for x in out]}},
                                             {"$set": {"transfer_ref": None}})
        raise
    return out


async def _rehome_allocation(so_id: str, roll: Dict[str, Any], dest: Dict[str, Any], transfer: Dict[str, Any]) -> None:
    """Komitmen SO ikut pindah alamat: baris alokasi & tugas outbound (belum mulai) pindah ke gudang tujuan."""
    so = await db.sales_orders.find_one({"id": so_id}, {"_id": 0, "allocations": 1})
    allocs = list((so or {}).get("allocations") or [])
    src = next((a for a in allocs if any(x.get("roll_id") == roll["id"] for x in a.get("rolls") or [])), None)
    if not src or src.get("warehouse_id") == dest["id"]:
        return
    entry = next(x for x in src["rolls"] if x.get("roll_id") == roll["id"])
    src["rolls"] = [x for x in src["rolls"] if x.get("roll_id") != roll["id"]]
    ln = float(entry.get("length") or roll.get("length_remaining") or 0)
    src["quantity"] = round(max(float(src.get("quantity") or 0) - ln, 0.0), 2)
    dst = next((a for a in allocs if a.get("product_id") == src["product_id"] and a.get("warehouse_id") == dest["id"]
                and a.get("owner_entity_id") == src.get("owner_entity_id") and a.get("via_transfer_id") == transfer["id"]), None)
    if not dst:
        dst = {**{k: v for k, v in src.items() if k not in ("id", "rolls", "quantity")}, "id": new_id("alloc"),
               "warehouse_id": dest["id"], "warehouse_name": dest.get("name", ""), "warehouse_city": dest.get("city", ""),
               "rolls": [], "quantity": 0.0, "via_transfer_id": transfer["id"],
               "allocation_explanation": f"Dipindah dari {src.get('warehouse_name', '')} lewat transfer {transfer.get('code')}."}
        allocs.append(dst)
    dst["rolls"].append(entry)
    dst["quantity"] = round(float(dst["quantity"]) + ln, 2)
    allocs = [a for a in allocs if a.get("rolls")]
    await db.sales_orders.update_one({"id": so_id}, {"$set": {"allocations": allocs, "updated_at": now_iso()},
                                                     "$addToSet": {"linked_transfer_ids": transfer["id"]}})
    src_task = await db.wms_tasks.find_one({"allocation_id": src["id"], "flow_type": "outbound", "status": "created"}, {"_id": 0})
    if not src_task:
        return
    left = round(float(src_task.get("quantity") or 0) - ln, 2)
    if left <= 0.01:
        await db.wms_tasks.update_one({"id": src_task["id"]}, {"$set": {"status": "cancelled", "quantity": 0.0,
                                      "cancel_reason": f"Roll dipindah ke {dest.get('name')} ({transfer.get('code')})",
                                      "updated_at": now_iso()}})
    else:
        await db.wms_tasks.update_one({"id": src_task["id"]}, {"$set": {"quantity": left, "updated_at": now_iso()}})
    got = await db.wms_tasks.find_one_and_update({"allocation_id": dst["id"], "flow_type": "outbound", "status": "created"},
                                                 [{"$set": {"quantity": {"$round": [{"$add": ["$quantity", ln]}, 2]},
                                                            "updated_at": now_iso()}}])
    if not got:
        await db.wms_tasks.insert_one({**src_task, "id": new_id("wms"), "allocation_id": dst["id"], "quantity": round(ln, 2),
                                       "picked_qty": 0.0, "shipped_qty": 0.0, "warehouse_id": dest["id"],
                                       "warehouse_name": dest.get("name", ""), "warehouse_city": dest.get("city", ""),
                                       "bin_id": "", "scan_log": [], "status": "created", "via_transfer_id": transfer["id"],
                                       "created_at": now_iso(), "updated_at": now_iso()})


# ─── Penerimaan aktual per roll (IMP-27) ───────────────────────────────────────
async def _exception(transfer_id: str, kind: str, actor: Dict[str, Any], **kw) -> Dict[str, Any]:
    exc = {"id": new_id("tex"), "kind": kind, "status": kw.pop("status", "open"), "roll_id": kw.pop("roll_id", ""),
           "roll_no": kw.pop("roll_no", ""), "code": kw.pop("code", ""), "reason": kw.pop("reason", ""),
           "evidence": kw.pop("evidence", ""), "by": actor.get("name", ""), "by_id": actor.get("id", ""),
           "at": now_iso(), **kw}
    await db.warehouse_transfers.update_one({"id": transfer_id}, {"$push": {"exceptions": exc}, "$set": {"updated_at": now_iso()}})
    return exc


def _open_exc(transfer: Dict[str, Any], kind: str, roll_id: str) -> Optional[Dict[str, Any]]:
    return next((e for e in transfer.get("exceptions") or [] if e.get("status") == "open" and e.get("kind") == kind
                 and e.get("roll_id") == roll_id), None)


async def _find_roll(transfer: Dict[str, Any], ref: str) -> Optional[Dict[str, Any]]:
    ids = _roll_ids(transfer)
    key = (ref or "").strip()
    if not key:
        return None
    r = await db.inventory_rolls.find_one({"id": {"$in": ids}, "$or": [{"id": key}, {"roll_no": key}]}, {"_id": 0})
    if r:
        return r
    tag = await db.rfid_tags.find_one({"$or": [{"epc": key}, {"code": key}, {"tag_code": key}], "roll_id": {"$in": ids}},
                                      {"_id": 0, "roll_id": 1})
    return await db.inventory_rolls.find_one({"id": tag["roll_id"]}, {"_id": 0}) if tag else None


async def _land(roll: Dict[str, Any], transfer: Dict[str, Any], dest: Dict[str, Any], status_kind: str,
                actor: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """in_transit_transfer → fisik di tujuan (CAS). None bila sudah diproses (retry)."""
    so_id = (roll.get("transfer_ref") or {}).get("so_id")
    keep = bool(so_id) and await so_still_open(so_id)
    # komitmen SO kembali ke status asalnya (reserved / committed) saat tiba
    status = {"damaged": "damaged", "hold": "hold"}.get(status_kind) or (
        (roll.get("transfer_prior_status") if roll.get("transfer_prior_status") in SO_HELD else "reserved") if keep else "available")
    src_wh = roll["warehouse_id"]
    res = await db.inventory_rolls.update_one(held_cas(roll), {"$set": {
        "warehouse_id": dest["id"], "status": status, "reserved_ref": roll.get("reserved_ref") if keep else None,
        "transfer_ref": None, "transfer_prior_status": None, "bin_id": None, "bin_code": "",
        "last_transfer": {"ref_id": transfer["id"], "code": transfer.get("code"), "from_warehouse_id": src_wh,
                          "date": now_iso(), "received_by": actor.get("name"), "outcome": status_kind},
        "updated_at": now_iso()}})
    if not res.matched_count:
        return None
    await db.rfid_tags.update_many({"roll_id": roll["id"], "status": "active"},
                                   {"$set": {"warehouse_id": dest["id"], "updated_at": now_iso()}})
    qty = round(float(roll.get("length_remaining") or 0), 2)
    await db.inventory_movements.insert_one({
        "id": new_id("mov"), "product_id": roll["product_id"], "warehouse_id": dest["id"],
        "owner_entity_id": roll["owner_entity_id"], "movement_type": "transfer_in", "quantity": qty,
        "unit": roll.get("unit", "meter"), "lot": roll.get("lot", ""), "batch": roll.get("batch", ""),
        "roll_id": roll["id"], "qty_rolls": 1, "receipt_outcome": status_kind, "by": actor.get("name"),
        "source_document": f"transfer_{transfer.get('code')}", "timestamp": now_iso()})
    for w in {src_wh, dest["id"]}:
        await rebuild_balance(roll["product_id"], w, roll["owner_entity_id"])
    if keep and status in SO_HELD:
        await _rehome_allocation(so_id, roll, dest, transfer)
    return {**roll, "warehouse_id": dest["id"], "status": status, "bin_id": None}


async def _refresh_status(transfer_id: str) -> Dict[str, Any]:
    t = await db.warehouse_transfers.find_one({"id": transfer_id}, {"_id": 0})
    in_transit = await transfer_held_rolls(transfer_id, ["in_transit_transfer"])
    received = await db.inventory_rolls.count_documents({"last_transfer.ref_id": transfer_id})
    if t["status"] in ("dispatched", "partially_received"):
        new = "completed" if not in_transit else ("partially_received" if received else "dispatched")
        upd = {"status": new, "updated_at": now_iso()}
        if new == "completed":
            upd.update({"completed_at": now_iso(), "completion_basis": "actual_receipt"})
        t = await db.warehouse_transfers.find_one_and_update({"id": transfer_id, "status": t["status"]}, {"$set": upd},
                                                             projection={"_id": 0}, return_document=True) or t
    return t


async def receive(transfer: Dict[str, Any], body: Any, actor: Dict[str, Any]) -> Dict[str, Any]:
    if transfer.get("transfer_kind") == "inter_entity":
        raise HTTPException(status_code=400, detail="Transfer antar badan usaha tidak memindah fisik — tidak ada penerimaan.")
    if transfer["status"] not in ("dispatched", "partially_received"):
        raise HTTPException(status_code=400, detail="Penerimaan hanya untuk transfer yang sudah dikirim (dalam perjalanan).")
    dest = await db.warehouses.find_one({"id": transfer["dest_warehouse_id"]}, {"_id": 0})
    node = pr.resolve_bin(dest, body.bin_id) if body.bin_id else None
    if body.bin_id and not node:
        raise HTTPException(status_code=400, detail="Bin/staging tujuan tidak ada di gudang tujuan.")
    override = (body.rule_exception_reason or "").strip()
    if override:
        pr.assert_supervisor(actor, "memberi pengecualian aturan gudang saat terima")
        _reason(override, "Alasan pengecualian aturan")
    results: List[Dict[str, Any]] = []
    # Validasi SEMUA baris dulu — tidak ada roll yang mendarat bila satu baris tidak sah.
    for ln in body.lines:
        if ln.outcome not in ("received", "damaged"):
            raise HTTPException(status_code=400, detail="Kondisi tiba hanya 'received' (baik) atau 'damaged' (rusak).")
        if ln.outcome == "damaged":
            _reason(ln.note, "Keterangan kerusakan")
    for ln in body.lines:
        ref = ln.roll_id or ln.code
        roll = await _find_roll(transfer, ref)
        if not roll:
            exc = await _exception(transfer["id"], "wrong_roll", actor, code=ref, reason=ln.note or "Roll tidak ada di transfer ini",
                                   status="open")
            results.append({"ref": ref, "result": "wrong_roll", "exception_id": exc["id"],
                            "message": "Roll ini bukan bagian transfer — tidak dimasukkan ke stok."})
            continue
        base = {"ref": ref, "roll_id": roll["id"], "roll_no": roll.get("roll_no")}
        if (roll.get("last_transfer") or {}).get("ref_id") == transfer["id"] and roll.get("status") != "in_transit_transfer":
            results.append({**base, "result": "already", "message": "Sudah diterima sebelumnya (tidak menambah stok)."})
            continue
        if roll.get("status") != "in_transit_transfer" or not owned_by_transfer(roll, transfer["id"]):
            results.append({**base, "result": "not_in_transit", "message": f"Roll berstatus {roll.get('status')} — bukan dalam perjalanan transfer ini."})
            continue
        prod = await db.products.find_one({"id": roll["product_id"]}, {"_id": 0}) or {}
        kind = "damaged" if ln.outcome == "damaged" else "received"
        viol = await pr.warehouse_violations(dest, roll, prod)
        if viol and kind == "received":
            if not override:
                if not _open_exc(transfer, "rule_violation", roll["id"]):
                    await _exception(transfer["id"], "rule_violation", actor, roll_id=roll["id"], roll_no=roll.get("roll_no"),
                                     reason=" | ".join(viol[:3]), system=True)
                results.append({**base, "result": "blocked_rules", "violations": viol,
                                "message": "Aturan gudang tujuan menolak roll ini — tetap dalam perjalanan sampai supervisor memutuskan."})
                continue
            kind = "hold"
        landed = await _land(roll, transfer, dest, kind, actor)
        if not landed:
            results.append({**base, "result": "already", "message": "Sudah diproses petugas lain (tidak menambah stok)."})
            continue
        if kind == "damaged":
            await _exception(transfer["id"], "damaged", actor, roll_id=roll["id"], roll_no=roll.get("roll_no"),
                             reason=_reason(ln.note, "Keterangan kerusakan"), evidence=ln.evidence or "",
                             committed_so=(roll.get("transfer_ref") or {}).get("so_id") or "")
        if kind == "hold":
            for e in transfer.get("exceptions") or []:
                if e.get("status") == "open" and e.get("kind") == "rule_violation" and e.get("roll_id") == roll["id"]:
                    await _resolve_exc(transfer["id"], e["id"], "received_hold", override, actor)
            if not _open_exc(transfer, "rule_violation", roll["id"]):
                await _exception(transfer["id"], "rule_violation", actor, roll_id=roll["id"], roll_no=roll.get("roll_no"),
                                 reason=" | ".join(viol[:3]), status="resolved", resolution="received_hold",
                                 resolution_reason=override, resolved_by=actor.get("name"), resolved_at=now_iso())
        row = {**base, "result": kind, "status": landed["status"]}
        if node and landed["status"] not in ("damaged", "hold"):
            from services.location_service import place_roll
            try:
                p = await place_roll(landed, dest, node, actor=actor, cas={"status": landed["status"]})
                row["bin_code"] = p["bin_code"]
            except HTTPException as exc:
                row["placement_error"] = exc.detail if isinstance(exc.detail, str) else (exc.detail or {}).get("message")
        results.append(row)
    await db.warehouse_transfers.update_one({"id": transfer["id"]}, {"$push": {"receipt_events": {
        "id": new_id("trc"), "by": actor.get("name"), "at": now_iso(), "note": (body.note or "")[:300],
        "bin_id": body.bin_id or "", "results": [{k: r.get(k) for k in ("ref", "roll_id", "result")} for r in results]}}})
    t = await _refresh_status(transfer["id"])
    return {"results": results, "transfer_status": t["status"], "summary": await summary(t)}


# ─── Exception & pemulihan ─────────────────────────────────────────────────────
async def _resolve_exc(transfer_id: str, exc_id: str, resolution: str, reason: str, actor: Dict[str, Any]) -> None:
    await db.warehouse_transfers.update_one(
        {"id": transfer_id, "exceptions.id": exc_id},
        {"$set": {"exceptions.$.status": "resolved", "exceptions.$.resolution": resolution,
                  "exceptions.$.resolution_reason": reason, "exceptions.$.resolved_by": actor.get("name"),
                  "exceptions.$.resolved_at": now_iso(), "updated_at": now_iso()}})


async def report(transfer: Dict[str, Any], body: Any, actor: Dict[str, Any]) -> Dict[str, Any]:
    if body.kind not in EXC_KINDS - {"rule_violation", "damaged"}:
        raise HTTPException(status_code=400, detail="Jenis exception: missing, wrong_roll, atau other.")
    if transfer["status"] not in ("dispatched", "partially_received"):
        raise HTTPException(status_code=400, detail="Exception penerimaan hanya untuk transfer dalam perjalanan.")
    reason = _reason(body.reason)
    roll = await _find_roll(transfer, body.roll_id) if body.roll_id else None
    if body.kind == "missing":
        if not roll or roll.get("status") != "in_transit_transfer":
            raise HTTPException(status_code=400, detail="Roll hilang harus roll transfer ini yang masih dalam perjalanan.")
        if _open_exc(transfer, "missing", roll["id"]):
            raise HTTPException(status_code=409, detail="Roll ini sudah dilaporkan hilang.")
    exc = await _exception(transfer["id"], body.kind, actor, roll_id=(roll or {}).get("id", ""),
                           roll_no=(roll or {}).get("roll_no", ""), code=body.code or "", reason=reason,
                           evidence=body.evidence or "")
    return {"exception": exc, "summary": await summary(await db.warehouse_transfers.find_one({"id": transfer["id"]}, {"_id": 0}))}


async def resolve(transfer: Dict[str, Any], exc_id: str, body: Any, actor: Dict[str, Any]) -> Dict[str, Any]:
    pr.assert_supervisor(actor, "menyelesaikan exception transfer")
    exc = next((e for e in transfer.get("exceptions") or [] if e["id"] == exc_id), None)
    if not exc or exc.get("status") != "open":
        raise HTTPException(status_code=404, detail="Exception terbuka tidak ditemukan.")
    reason = _reason(body.reason)
    if body.action == "return_to_source":
        roll = await db.inventory_rolls.find_one({"id": exc.get("roll_id")}, {"_id": 0}) if exc.get("roll_id") else None
        if not roll or roll.get("status") != "in_transit_transfer" or not owned_by_transfer(roll, transfer["id"]):
            raise HTTPException(status_code=400, detail="Roll exception ini tidak lagi dalam perjalanan.")
        so_id = (roll.get("transfer_ref") or {}).get("so_id")
        keep = bool(so_id) and await so_still_open(so_id)
        res = await db.inventory_rolls.update_one(held_cas(roll), {"$set": {
            "status": "reserved" if keep else "available", "reserved_ref": roll.get("reserved_ref") if keep else None,
            "transfer_ref": None, "returned_from_transfer": {"ref_id": transfer["id"], "at": now_iso(), "reason": reason},
            "updated_at": now_iso()}})
        if res.matched_count:
            await db.inventory_movements.insert_one({
                "id": new_id("mov"), "product_id": roll["product_id"], "warehouse_id": roll["warehouse_id"],
                "owner_entity_id": roll["owner_entity_id"], "movement_type": "transfer_cancelled",
                "quantity": round(float(roll.get("length_remaining") or 0), 2), "unit": roll.get("unit", "meter"),
                "lot": roll.get("lot", ""), "roll_id": roll["id"], "qty_rolls": 1, "by": actor.get("name"),
                "source_document": f"transfer_{transfer.get('code')}:kembali", "timestamp": now_iso()})
            await rebuild_balance(roll["product_id"], roll["warehouse_id"], roll["owner_entity_id"])
    elif body.action != "close_note":
        raise HTTPException(status_code=400, detail="Tindakan: return_to_source atau close_note.")
    if body.action == "close_note" and exc["kind"] in ("missing", "rule_violation"):
        raise HTTPException(status_code=400, detail=(
            "Roll hilang/ditolak aturan tidak bisa ditutup dengan catatan saja — terima roll itu (dengan pengecualian) "
            "atau kembalikan ke gudang asal. Penghapusan stok hilang menunggu keputusan Finance (DEC-13)."))
    await _resolve_exc(transfer["id"], exc_id, body.action, reason, actor)
    t = await _refresh_status(transfer["id"])
    return {"transfer_status": t["status"], "summary": await summary(t)}


# ─── Ringkasan (sumber kebenaran = dokumen roll) ───────────────────────────────
async def summary(transfer: Dict[str, Any]) -> Dict[str, Any]:
    ids = _roll_ids(transfer)
    rolls = {r["id"]: r for r in await db.inventory_rolls.find({"id": {"$in": ids}}, {"_id": 0}).to_list(len(ids) + 1)}
    refs = {x["roll_id"]: (it, x) for it in transfer.get("items") or [] for x in it.get("rolls") or []}
    rows, counts = [], {}
    for rid in ids:
        r = rolls.get(rid) or {}
        it, x = refs[rid]
        lt = r.get("last_transfer") or {}
        if r.get("status") == "in_transit_transfer" and owned_by_transfer(r, transfer["id"]):
            state = "in_transit"
        elif lt.get("ref_id") == transfer["id"]:
            state = {"damaged": "received_damaged", "hold": "received_hold"}.get(lt.get("outcome"), "received")
        elif (r.get("returned_from_transfer") or {}).get("ref_id") == transfer["id"]:
            state = "returned"
        elif owned_by_transfer(r, transfer["id"]) and r.get("status") == "reserved":
            state = "waiting_dispatch"
        else:
            state = "legacy_completed" if transfer["status"] == "completed" else "released"
        counts[state] = counts.get(state, 0) + 1
        rows.append({"roll_id": rid, "roll_no": x.get("roll_no"), "lot": x.get("lot"), "length": x.get("length"),
                     "unit": it.get("unit"), "sku": it.get("sku"), "product_name": it.get("product_name"), "state": state,
                     "status": r.get("status"), "warehouse_id": r.get("warehouse_id"), "bin_code": r.get("bin_code") or "",
                     "committed_so": (x.get("committed_so") or ""), "received_by": lt.get("received_by") if lt.get("ref_id") == transfer["id"] else ""})
    legacy = transfer["status"] == "completed" and not transfer.get("receipt_events") and transfer.get("transfer_kind") != "inter_entity"
    dest = await db.warehouses.find_one({"id": transfer.get("dest_warehouse_id")}, {"_id": 0}) or {}
    bins = [{"id": n["bin"]["id"], "code": n["bin"].get("code", ""), "path": n["path"],
             "function": pr.effective(dest, n)["function"]} for n in pr.flatten_nodes(dest)] if dest else []
    bins.sort(key=lambda b: (b["function"] != "staging", b["code"]))
    exc = transfer.get("exceptions") or []
    return {"rolls": rows, "counts": counts, "total": len(ids),
            "exceptions": exc, "open_exceptions": sum(1 for e in exc if e.get("status") == "open"),
            "legacy_note": ("Transfer lama: hanya status 'Selesai' yang tercatat, tanpa bukti penerimaan per roll."
                            if legacy else ""),
            "receipt_events": transfer.get("receipt_events") or [], "dest_bins": bins[:300],
            "sales_order_id": transfer.get("sales_order_id") or "", "sales_order_number": transfer.get("sales_order_number") or ""}


# ─── Sisa P02: transfer antar badan usaha memakai evaluator yang sama ──────────
async def interco_violations(transfer: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Ownership-in-place: barang tetap di gudangnya tetapi pemiliknya berganti → gudang itu wajib boleh
    dipakai badan usaha TUJUAN (shared/dedicated) dan lolos rules gudang."""
    out: List[Dict[str, Any]] = []
    whs: Dict[str, Any] = {}
    for it in transfer.get("items") or []:
        prod = await db.products.find_one({"id": it["product_id"]}, {"_id": 0}) or {}
        for x in it.get("rolls") or []:
            r = await db.inventory_rolls.find_one({"id": x["roll_id"]}, {"_id": 0})
            if not r:
                continue
            wid = r.get("warehouse_id")
            if wid not in whs:
                whs[wid] = await db.warehouses.find_one({"id": wid}, {"_id": 0}) or {}
            v = await pr.warehouse_violations(whs[wid], {**r, "owner_entity_id": transfer.get("dest_entity_id")}, prod)
            if v:
                out.append({"roll_id": r["id"], "roll_no": r.get("roll_no"), "warehouse": whs[wid].get("name", wid),
                            "violations": v})
    return out
