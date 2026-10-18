"""LN-093 — tujuan barang retur berantai Sukacita → CST → supplier.

Tahap 1 (pemilik = PT pembeli internal, mis. Sukacita): `keep` (pemilik tetap) atau
`return_internal` (retur antar-PT berpasangan; CST wajib menerima; posisi fisik shared tetap).
Tahap 2 (pemilik = PT penjual internal, mis. CST): `keep`, `supplier_return` (selama masa
retur supplier belum lewat) atau `dispose` (BS dibuang dengan foto bukti + jurnal write-off).
Masa retur supplier lewat → otomatis `keep`, status roll TIDAK diubah (QC/grade/hold tetap berlaku).
Klaim atomik per roll → retry/klik ganda tidak melipatgandakan dokumen.
"""
from typing import Any, Dict, List

from core_utils import new_id, now_iso, rupiah, timeline_entry
from db import db
from services import gl_service
from services import interco_return_service as icret
from services.return_policy_service import return_assumptions, supplier_deadlines
from services.return_service import interco_origin_of_roll
from services.roll_service import rebuild_balance

STAGE1 = {"keep": "Simpan di pemilik sekarang", "return_internal": "Kembalikan ke PT pemasok internal"}
STAGE2 = {"keep": "Simpan sebagai stok", "supplier_return": "Retur ke supplier", "dispose": "Buang (BS) dengan bukti"}
GONE = ("consumed", "returned_supplier", "damaged", "sold")
UNSELLABLE_GRADES = ("BS",)


class DispositionError(ValueError):
    pass


def _today() -> str:
    return now_iso()[:10]


async def _rolls(return_id: str, roll_ids: List[str] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"return_id": return_id, "origin_type": "return"}
    if roll_ids:
        q["id"] = {"$in": list(roll_ids)}
    return await db.inventory_rolls.find(q, {"_id": 0}).to_list(1000)


def _stage(r: Dict[str, Any], origin: Dict[str, Any]) -> str:
    disp = r.get("disposition") or {}
    if r.get("status") in GONE:
        return "closed"
    if not origin:
        return "no_internal_origin"
    owner = r.get("owner_entity_id")
    if owner == origin.get("buyer_entity_id"):
        if not disp.get("internal"):
            return "internal_pending" if r.get("status") == "available" else "awaiting_release"
        return "kept_internal" if disp["internal"]["decision"] == "keep" else "internal_in_progress"
    if owner == origin.get("seller_entity_id"):
        return "supplier_pending" if not disp.get("supplier") else f"supplier_{disp['supplier']['decision']}"
    return "other_owner"


def _sellable(r: Dict[str, Any]) -> bool:
    return r.get("status") == "available" and not r.get("hold") and (r.get("grade") or "") not in UNSELLABLE_GRADES


async def _auto_keep(r: Dict[str, Any]) -> bool:
    entry = {"decision": "keep", "auto": True, "status": "done", "by": "sistem", "at": now_iso(),
             "reason": "Masa retur supplier lewat — disimpan sebagai stok (status QC/grade tidak diubah)."}
    res = await db.inventory_rolls.update_one({"id": r["id"], "disposition.supplier": {"$exists": False}},
                                              {"$set": {"disposition.supplier": entry}})
    if res.modified_count:
        r.setdefault("disposition", {})["supplier"] = entry
    return bool(res.modified_count)


async def _heal_cancelled(r: Dict[str, Any]) -> None:
    """Retur internal dibatalkan pengembali → roll kembali menunggu keputusan tahap 1."""
    rp = ((r.get("disposition") or {}).get("internal") or {}).get("return_pair_id")
    if rp and await db.interco_returns.find_one({"return_pair_id": rp, "status": "cancelled"}, {"_id": 0, "id": 1}):
        await db.inventory_rolls.update_one({"id": r["id"], "disposition.internal.return_pair_id": rp},
                                            {"$unset": {"disposition.internal": ""}})
        r["disposition"].pop("internal", None)


async def view(ret: Dict[str, Any]) -> Dict[str, Any]:
    a = await return_assumptions(ret.get("entity_id", ""))
    window = int(a.get("supplier_window_days") or 21)
    rolls = await _rolls(ret["id"])
    dl = {rid: g for g in await supplier_deadlines(rolls, window) for rid in g["roll_ids"]}
    names = {e["id"]: e.get("short_name") or e["id"] async for e in
             db.business_entities.find({}, {"_id": 0, "id": 1, "short_name": 1})}
    rows = []
    for r in rolls:
        await _heal_cancelled(r)
        origin = await interco_origin_of_roll(r)
        g = dl.get(r["id"]) or {}
        expired = bool(g.get("deadline")) and g["deadline"][:10] < _today()
        stage = _stage(r, origin)
        if stage == "supplier_pending" and expired and await _auto_keep(r):
            stage = "supplier_keep"
        disp = r.get("disposition") or {}
        rows.append({
            "roll_id": r["id"], "roll_no": r.get("roll_no", ""), "product_id": r.get("product_id", ""),
            "qty": round(float(r.get("length_remaining") or 0), 2), "unit": r.get("unit", ""),
            "grade": r.get("grade", ""), "status": r.get("status", ""), "warehouse_id": r.get("warehouse_id", ""),
            "owner_entity_id": r.get("owner_entity_id", ""), "owner_name": names.get(r.get("owner_entity_id"), ""),
            "origin_interco_number": origin.get("number", ""),
            "buyer_name": names.get(origin.get("buyer_entity_id"), ""),
            "seller_name": names.get(origin.get("seller_entity_id"), ""),
            "supplier_name": r.get("supplier_name") or g.get("supplier_name", ""),
            "po_number": r.get("po_number") or g.get("po_number", ""),
            "supplier_deadline": (g.get("deadline") or "")[:10], "supplier_window_expired": expired,
            "stage": stage, "internal": disp.get("internal"), "supplier": disp.get("supplier"),
            "sellable": _sellable(r),
        })
    return {"rows": rows, "supplier_window_days": window, "stage1_options": STAGE1, "stage2_options": STAGE2}


async def _claim(roll_ids: List[str], key: str, entry: Dict[str, Any]) -> None:
    done: List[str] = []
    for rid in roll_ids:
        res = await db.inventory_rolls.update_one({"id": rid, f"disposition.{key}": {"$exists": False}},
                                                  {"$set": {f"disposition.{key}": entry}})
        if not res.modified_count:
            await _release(done, key)
            raise DispositionError("Sebagian roll sudah diputuskan (atau sedang diproses) — muat ulang halaman.")
        done.append(rid)


async def _release(roll_ids: List[str], key: str) -> None:
    if roll_ids:
        await db.inventory_rolls.update_many({"id": {"$in": roll_ids}}, {"$unset": {f"disposition.{key}": ""}})


async def _finish(roll_ids: List[str], key: str, extra: Dict[str, Any]) -> None:
    await db.inventory_rolls.update_many({"id": {"$in": roll_ids}},
                                         {"$set": {f"disposition.{key}.{k}": v for k, v in {"status": "done", **extra}.items()}})


async def _log(ret: Dict[str, Any], title: str, actor: str, note: str) -> None:
    await db.sales_returns.update_one({"id": ret["id"]}, {"$push": {"disposition_log": timeline_entry("disposition", title, actor, note)},
                                                         "$set": {"updated_at": now_iso()}})


async def _pick(ret: Dict[str, Any], roll_ids: List[str], stage: str) -> List[Dict[str, Any]]:
    if not roll_ids:
        raise DispositionError("Pilih minimal satu roll.")
    rows = {x["roll_id"]: x for x in (await view(ret))["rows"]}
    bad = [rows.get(r, {}).get("roll_no") or r for r in roll_ids if rows.get(r, {}).get("stage") != stage]
    if bad:
        raise DispositionError(f"Roll {', '.join(bad[:10])} tidak sedang menunggu keputusan tahap ini.")
    owners = {rows[r]["owner_entity_id"] for r in roll_ids}
    if len(owners) > 1:
        raise DispositionError("Roll yang dipilih dimiliki lebih dari satu PT — putuskan per pemilik.")
    return [rows[r] for r in roll_ids]


async def decide_internal(ret: Dict[str, Any], roll_ids: List[str], decision: str, reason: str,
                          actor: str) -> Dict[str, Any]:
    if decision not in STAGE1:
        raise DispositionError("Keputusan tahap 1 tidak dikenal.")
    if len((reason or "").strip()) < 5:
        raise DispositionError("Alasan wajib diisi (minimal 5 huruf).")
    picked = await _pick(ret, roll_ids, "internal_pending")
    entry = {"decision": decision, "status": "processing", "reason": reason.strip(), "by": actor, "at": now_iso()}
    await _claim(roll_ids, "internal", entry)
    if decision == "keep":
        await _finish(roll_ids, "internal", {})
        await _log(ret, "Barang retur disimpan pemilik", actor, f"{len(roll_ids)} roll tetap milik {picked[0]['owner_name']}")
        return {"decision": decision, "rolls": len(roll_ids), "interco_returns": []}
    rolls = {r["id"]: r for r in await _rolls(ret["id"], roll_ids)}
    groups: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for rid in roll_ids:
        origin = await interco_origin_of_roll(rolls[rid])
        g = groups.setdefault(origin["interco_id"], {}).setdefault(rolls[rid]["product_id"], {"qty": 0.0, "roll_ids": []})
        g["qty"] += float(rolls[rid].get("length_remaining") or 0)
        g["roll_ids"].append(rid)
    created = []
    for interco_id, by_prod in groups.items():
        grp_rolls = [x for g in by_prod.values() for x in g["roll_ids"]]
        try:
            pair = await icret.create({
                "interco_id": interco_id, "reason": reason.strip(), "source_sales_return_id": ret["id"],
                "notes": f"LN-093 retur internal dari retur pelanggan {ret.get('number', '')}",
                "items": [{"product_id": pid, "quantity": round(g["qty"], 4), "roll_ids": g["roll_ids"]}
                          for pid, g in by_prod.items()]}, actor)
        except Exception:
            await _release([r for r in roll_ids if r not in {x for c in created for x in c["roll_ids"]}], "internal")
            raise
        rp = pair["returner"]["return_pair_id"]
        await db.interco_returns.update_many({"return_pair_id": rp}, {"$set": {"mandatory_accept": True}})
        await _finish(grp_rolls, "internal", {"interco_return_id": pair["returner"]["id"],
                                              "interco_return_number": pair["returner"]["number"], "return_pair_id": rp})
        created.append({"id": pair["returner"]["id"], "number": pair["returner"]["number"],
                        "counterpart_number": pair["receiver"]["number"], "roll_ids": grp_rolls})
    await _log(ret, "Retur internal dibuat", actor, ", ".join(c["number"] for c in created) + " — PT pemasok wajib menerima")
    return {"decision": decision, "rolls": len(roll_ids), "interco_returns": created}


async def _dispose(ret: Dict[str, Any], rolls: List[Dict[str, Any]], reason: str, actor: str) -> float:
    total = 0.0
    combos = set()
    for r in rolls:
        qty = float(r.get("length_remaining") or 0)
        amount = round(qty * float(r.get("unit_cost") or r.get("base_unit_cost") or 0), 2)
        je = await gl_service.post_inventory_writeoff(roll_id=r["id"], entity_id=r.get("owner_entity_id", ""),
                                                       amount=amount, reason=f"BS dibuang · {reason}",
                                                       label=f"{r.get('roll_no') or r['id']} (retur {ret.get('number', '')})")
        await db.inventory_rolls.update_one({"id": r["id"]}, {"$set": {
            "status": "damaged", "length_remaining": 0, "disposed_qty": qty, "disposed_at": now_iso(),
            "writeoff_amount": amount, "writeoff_je_id": (je or {}).get("id", ""), "updated_at": now_iso()}})
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": r["product_id"], "warehouse_id": r.get("warehouse_id", ""),
            "owner_entity_id": r.get("owner_entity_id", ""), "type": "return_disposal", "movement_type": "return_disposal",
            "direction": "out", "quantity": round(qty, 2), "unit": r.get("unit", ""), "roll_id": r["id"], "qty_rolls": 1,
            "ref_type": "sales_return", "ref_id": ret["id"], "source_document": ret["id"], "timestamp": now_iso(),
            "notes": f"BS dibuang (retur {ret.get('number', '')}) · {reason} · write-off {rupiah(amount)}"})
        combos.add((r["product_id"], r.get("warehouse_id", ""), r.get("owner_entity_id", "")))
        total += amount
    for pid, wid, eid in combos:
        await rebuild_balance(pid, wid, eid)
    return round(total, 2)


async def decide_supplier(ret: Dict[str, Any], roll_ids: List[str], decision: str, reason: str,
                          attachment_ids: List[str], actor: str) -> Dict[str, Any]:
    if decision not in STAGE2:
        raise DispositionError("Keputusan tahap 2 tidak dikenal.")
    if len((reason or "").strip()) < 5:
        raise DispositionError("Alasan wajib diisi (minimal 5 huruf).")
    picked = await _pick(ret, roll_ids, "supplier_pending")
    if decision == "supplier_return" and any(p["supplier_window_expired"] for p in picked):
        raise DispositionError("Masa retur supplier sudah lewat untuk sebagian roll — simpan sebagai stok.")
    if decision == "dispose":
        atts = {a["id"]: a for a in (ret.get("attachments") or []) + (ret.get("disposition_photos") or [])
                if not a.get("is_deleted")}
        if not any((atts.get(i, {}).get("content_type") or "").startswith("image/") for i in attachment_ids or []):
            raise DispositionError("Buang BS wajib melampirkan minimal satu foto bukti.")
    entry = {"decision": decision, "status": "processing", "reason": reason.strip(), "by": actor, "at": now_iso(),
             "attachment_ids": list(attachment_ids or [])}
    await _claim(roll_ids, "supplier", entry)
    out: Dict[str, Any] = {"decision": decision, "rolls": len(roll_ids)}
    try:
        if decision == "supplier_return":
            from services import purchase_return_service as prs
            pr = await prs.create_from_sales_return(ret["id"], actor, roll_ids=roll_ids, reason=reason.strip(),
                                                    bypass_import_policy=False)
            out["purchase_returns"] = pr.get("split_purchase_returns") or []
            await _finish(roll_ids, "supplier", {"purchase_return_numbers": pr.get("number", "")})
            note = f"Retur supplier {pr.get('number', '')}"
        elif decision == "dispose":
            out["writeoff_total"] = await _dispose(ret, await _rolls(ret["id"], roll_ids), reason.strip(), actor)
            await _finish(roll_ids, "supplier", {"writeoff_total": out["writeoff_total"]})
            note = f"{len(roll_ids)} roll BS dibuang · write-off {rupiah(out['writeoff_total'])}"
        else:
            await _finish(roll_ids, "supplier", {})
            note = f"{len(roll_ids)} roll disimpan {picked[0]['owner_name']} (status QC/grade tidak diubah)"
    except Exception:
        await _release(roll_ids, "supplier")
        raise
    await _log(ret, f"Keputusan {STAGE2[decision].lower()}", actor, note)
    return out


_AWAIT_SUPPLIER = {"origin_type": "return", "disposition.internal.decision": "return_internal",
                   "disposition.supplier": {"$exists": False}, "status": {"$nin": list(GONE)}}


async def _pending_supplier_rows(scope_ids: List[str] = None) -> List[Dict[str, Any]]:
    """Kasus retur (dengan baris tahap 2 yang masih menunggu) milik PT dalam cakupan."""
    q = dict(_AWAIT_SUPPLIER)
    if scope_ids is not None:
        q["owner_entity_id"] = {"$in": scope_ids}
    rids = await db.inventory_rolls.distinct("return_id", q)
    out = []
    for rid in rids:
        ret = await db.sales_returns.find_one({"id": rid}, {"_id": 0})
        if not ret:
            continue
        v = await view(ret)
        rows = [r for r in v["rows"] if r["stage"] == "supplier_pending"
                and (scope_ids is None or r["owner_entity_id"] in scope_ids)]
        if rows:
            out.append({"return_id": rid, "return_number": ret.get("number", ""),
                        "supplier_window_days": v["supplier_window_days"], "rows": rows,
                        "photos": [{k: p.get(k) for k in ("id", "filename", "content_type")}
                                   for p in ret.get("disposition_photos") or []]})
    return out


async def inbox(scope_ids: List[str]) -> Dict[str, Any]:
    """Meja PT pemasok (CST): retur internal wajib terima + roll menunggu keputusan tahap 2.
    Detail pelanggan PT pengembali tidak ikut (hanya nomor retur sebagai acuan kasus)."""
    incoming = await db.interco_returns.find(
        {"role": "receiver", "mandatory_accept": True, "entity_id": {"$in": scope_ids},
         "status": {"$in": ["draft", "approved"]}},
        {"_id": 0, "id": 1, "number": 1, "counterpart_id": 1, "counterpart_number": 1, "status": 1,
         "buyer_entity_name": 1, "seller_entity_name": 1, "grand_total": 1, "reason": 1, "doc_date": 1,
         "warehouse_transfer_code": 1, "warehouse_transfer_status": 1, "source_sales_return_number": 1,
         "created_by": 1, "items.product_name": 1, "items.sku": 1, "items.quantity": 1, "items.unit": 1,
         "items.qty_rolls": 1}).sort("created_at", 1).to_list(200)
    cases = await _pending_supplier_rows(scope_ids)
    return {"incoming": incoming, "cases": cases,
            "counts": {"incoming": len(incoming), "rolls": sum(len(c["rows"]) for c in cases)}}


REMINDER_ROLES = ("warehouse_admin", "admin", "finance")


async def job_supplier_deadline_reminder() -> Dict[str, Any]:
    """LN-093 — ingatkan gudang/admin & finance PT pemilik N hari sebelum masa retur supplier habis."""
    from datetime import date
    from services.notification_service import create_notification
    today = date.fromisoformat(_today())
    sent = 0
    for case in await _pending_supplier_rows(None):
        for r in case["rows"]:
            if not r["supplier_deadline"]:
                continue
            a = await return_assumptions(r["owner_entity_id"])
            days = int(a.get("supplier_reminder_days") or 0)
            left = (date.fromisoformat(r["supplier_deadline"]) - today).days
            if days <= 0 or not 0 <= left <= days:
                continue
            for role in REMINDER_ROLES:
                n = await create_notification(
                    notif_type="return_supplier_deadline", severity="warning" if left <= 1 else "info",
                    title=f"Batas retur supplier {r['supplier_deadline']}: roll {r['roll_no']}",
                    body=(f"{r['qty']} {r['unit']} · {r['supplier_name'] or 'supplier'}{' · ' + r['po_number'] if r['po_number'] else ''}"
                          f" · {'hari ini' if left == 0 else f'{left} hari lagi'}. Putuskan simpan / retur supplier / buang BS "
                          "di Antar-PT → Retur Masuk; lewat batas otomatis disimpan sebagai stok."),
                    link="interco-transactions", entity_id=r["owner_entity_id"], recipient_role=role,
                    ref=f"{r['roll_id']}:{r['supplier_deadline']}:{role}", dedupe=True, dedupe_scope="ever")
                sent += 1 if n else 0
    return {"created": sent, "detail": f"{sent} pengingat batas retur supplier dikirim"}


async def desk_summary(scope_ids: List[str]) -> Dict[str, Any]:
    """Ringkasan Beranda PT pemasok: retur masuk, roll menunggu keputusan, batas supplier dekat."""
    from datetime import date
    box = await inbox(scope_ids)
    today = date.fromisoformat(_today())
    due = []
    for c in box["cases"]:
        for r in c["rows"]:
            if not r["supplier_deadline"]:
                continue
            a = await return_assumptions(r["owner_entity_id"])
            left = (date.fromisoformat(r["supplier_deadline"]) - today).days
            if 0 <= left <= int(a.get("supplier_reminder_days") or 3):
                due.append({"roll_no": r["roll_no"], "deadline": r["supplier_deadline"], "days_left": left,
                            "return_number": c["return_number"]})
    return {"incoming": box["counts"]["incoming"], "rolls": box["counts"]["rolls"],
            "due_soon": len(due), "due_items": sorted(due, key=lambda x: x["deadline"])[:5]}
