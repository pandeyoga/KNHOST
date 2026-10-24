"""UAT 24 Okt (P7) — dokumen Perbaikan (`repair_orders`, nomor RPR-…): roll jadi yang cacat / warnanya meleset
diperbaiki, dicelup ulang, atau di-finishing ulang — di dalam (internal) atau di mitra makloon — lalu kembali ke stok.

Alur: Draf → Dikirim (roll keluar dari ATP: status `wip` ber-`bucket_ref` perbaikan, fisik dicatat di mitra bila
eksternal) → Diterima (qty hasil per roll, susut, grade baru, dye lot baru) → Selesai. Batal: dari Draf, atau dari
Dikirim (roll kembali ke status semula).

Keputusan pemilik (usulan bawaan §4):
* P7-K1 — biaya perbaikan **dikapitalisasi** ke nilai persediaan roll hasil (HPP per satuan naik; susut ikut terserap).
  Jurnal: Dr Persediaan / Cr Hutang usaha (mitra) — tagihan mitra memakai Vendor Bill yang ada; perbaikan internal:
  Cr Overhead produksi diserap.
* P7-K2 — celup ulang **boleh berganti SKU** (warna lain): roll ANAK lahir ber-SKU baru, roll induk ditutup.
"""
from __future__ import annotations

from typing import Any, Dict, List

from db import db
from core_utils import new_id, next_doc_number, now_iso, rupiah

KINDS = {"perbaikan": "Perbaikan cacat", "celup_ulang": "Celup ulang (re-dye)", "finishing_ulang": "Finishing ulang"}
COST_BASIS = {"per_unit": "per satuan", "per_roll": "per roll", "lumpsum": "borongan"}
STATUS_LABEL = {"draft": "Draf", "sent": "Dikirim", "done": "Selesai", "cancelled": "Dibatalkan"}
ELIGIBLE_STATUSES = ("available", "quarantine", "damaged", "blocked", "hold")
REPAIR_STATUS = "wip"     # bucket WIP: tidak tersedia dijual (ATP), tetap dimiliki & dihitung persediaan
EPS = 0.005


class RepairError(ValueError):
    pass


def _label(ro: Dict[str, Any]) -> str:
    return f"Perbaikan {ro.get('number') or ro.get('id')}"


async def candidate_rolls(entity_id: str, q: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    """Roll yang boleh dikirim ke perbaikan: milik PT ini, di gudang (tersedia / karantina / rusak / ditahan), tanpa
    pesanan yang mencadangkannya, dan belum ada di dokumen perbaikan lain yang masih berjalan."""
    query: Dict[str, Any] = {"owner_entity_id": entity_id, "status": {"$in": list(ELIGIBLE_STATUSES)},
                             "length_remaining": {"$gt": EPS}, "reserved_ref": {"$in": [None, ""]},
                             "length_reserved": {"$in": [None, 0, 0.0]}, "repair_open": {"$in": [None, ""]}}
    if q.strip():
        rx = {"$regex": q.strip(), "$options": "i"}
        pids = [p["id"] async for p in db.products.find({"$or": [{"sku": rx}, {"name": rx}]}, {"_id": 0, "id": 1}).limit(200)]
        query["$or"] = [{"roll_no": rx}, {"lot": rx}, {"product_id": {"$in": pids}}]
    rows = await db.inventory_rolls.find(query, {"_id": 0, "id": 1, "roll_no": 1, "product_id": 1, "lot": 1, "grade": 1,
                                                 "length_remaining": 1, "unit": 1, "status": 1, "warehouse_id": 1}
                                         ).sort("roll_no", 1).to_list(limit)
    prods = {p["id"]: p async for p in db.products.find({"id": {"$in": list({r["product_id"] for r in rows})}},
                                                         {"_id": 0, "id": 1, "sku": 1, "name": 1})}
    for r in rows:
        p = prods.get(r["product_id"]) or {}
        r.update({"sku": p.get("sku", ""), "product_name": p.get("name", "")})
    return rows


async def _rolls_for_lines(entity_id: str, roll_ids: List[str]) -> List[Dict[str, Any]]:
    ids = list(dict.fromkeys([r for r in roll_ids if r]))
    if not ids:
        raise RepairError("Pilih minimal satu roll.")
    rows = {r["id"]: r async for r in db.inventory_rolls.find({"id": {"$in": ids}}, {"_id": 0})}
    out = []
    for rid in ids:
        r = rows.get(rid)
        if not r:
            raise RepairError(f"Roll {rid} tidak ditemukan.")
        tag = r.get("roll_no") or rid
        if r.get("owner_entity_id") != entity_id:
            raise RepairError(f"Roll {tag} milik badan usaha lain.")
        if r.get("status") not in ELIGIBLE_STATUSES:
            raise RepairError(f"Roll {tag} berstatus {r.get('status')} — hanya roll di gudang (tersedia/karantina/"
                              "rusak/ditahan) yang bisa dikirim ke perbaikan.")
        if r.get("reserved_ref") or float(r.get("length_reserved") or 0) > EPS:
            raise RepairError(f"Roll {tag} sedang dicadangkan pesanan — lepas cadangannya dulu.")
        if r.get("repair_open"):
            raise RepairError(f"Roll {tag} sudah ada di dokumen perbaikan lain yang masih berjalan.")
        out.append(r)
    return out


def _cost_total(cost: Dict[str, Any], lines: List[Dict[str, Any]], qty_key: str = "qty_sent") -> float:
    basis, rate = cost.get("basis") or "lumpsum", float(cost.get("rate") or 0)
    if basis == "per_unit":
        main = rate * sum(float(ln.get(qty_key) or 0) for ln in lines)
    elif basis == "per_roll":
        main = rate * len(lines)
    else:
        main = rate
    other = sum(float(o.get("amount") or 0) for o in cost.get("other_costs") or [])
    return round(main + other, 2)


def _norm_cost(raw: Dict[str, Any]) -> Dict[str, Any]:
    basis = (raw or {}).get("basis") or "lumpsum"
    if basis not in COST_BASIS:
        raise RepairError("Dasar biaya harus per_unit / per_roll / lumpsum.")
    rate = float((raw or {}).get("rate") or 0)
    if rate < 0:
        raise RepairError("Tarif tidak boleh negatif.")
    other = [{"label": (o.get("label") or "Biaya lain").strip(), "amount": round(float(o.get("amount") or 0), 2)}
             for o in (raw or {}).get("other_costs") or [] if float(o.get("amount") or 0) > 0]
    return {"basis": basis, "rate": rate, "other_costs": other, "contract_id": (raw or {}).get("contract_id") or ""}


async def create(data: Dict[str, Any], actor: Dict[str, Any], entity_id: str) -> Dict[str, Any]:
    kind = data.get("kind") or "perbaikan"
    if kind not in KINDS:
        raise RepairError("Jenis perbaikan tidak dikenal.")
    ptype = data.get("partner_type") or "internal"
    if ptype not in ("internal", "makloon"):
        raise RepairError("Pelaksana harus internal atau mitra makloon.")
    partner = {"partner_type": ptype, "partner_id": "", "partner_name": "Internal (gudang/produksi sendiri)"}
    if ptype == "makloon":
        pid = (data.get("partner_id") or "").strip()
        m = await db.makloons.find_one({"id": pid}, {"_id": 0, "id": 1, "name": 1}) if pid else None
        if not m:
            m = await db.suppliers.find_one({"id": pid}, {"_id": 0, "id": 1, "name": 1}) if pid else None
        if not m:
            raise RepairError("Pilih mitra makloon pelaksana perbaikan.")
        partner.update({"partner_id": m["id"], "partner_name": m.get("name", "")})
    target = {"product_id": "", "product_sku": "", "color_name": (data.get("target_color") or "").strip(),
              "dye_lot": (data.get("target_dye_lot") or "").strip()}
    if kind == "celup_ulang":
        if not (target["color_name"] or data.get("target_product_id")):
            raise RepairError("Celup ulang wajib menyebut warna tujuan (atau SKU tujuan).")
        if data.get("target_product_id"):
            tp = await db.products.find_one({"id": data["target_product_id"]}, {"_id": 0, "id": 1, "sku": 1, "status": 1})
            if not tp or tp.get("status") == "inactive":
                raise RepairError("SKU tujuan celup ulang tidak ditemukan / nonaktif.")
            target.update({"product_id": tp["id"], "product_sku": tp.get("sku", "")})
    rolls = await _rolls_for_lines(entity_id, data.get("roll_ids") or [])
    lines = [{"roll_id": r["id"], "roll_no": r.get("roll_no", ""), "product_id": r["product_id"],
              "qty_sent": round(float(r.get("length_remaining") or 0), 2), "unit": r.get("unit") or "",
              "grade_before": r.get("grade", ""), "lot_before": r.get("lot", ""), "prev_status": r.get("status"),
              "warehouse_id": r.get("warehouse_id", ""), "unit_cost_before": float(r.get("unit_cost") or r.get("base_unit_cost") or 0)}
             for r in rolls]
    prods = {p["id"]: p async for p in db.products.find({"id": {"$in": list({ln["product_id"] for ln in lines})}},
                                                         {"_id": 0, "id": 1, "sku": 1, "name": 1})}
    for ln in lines:
        ln.update({"sku": (prods.get(ln["product_id"]) or {}).get("sku", ""),
                   "product_name": (prods.get(ln["product_id"]) or {}).get("name", "")})
    cost = _norm_cost(data.get("cost") or {})
    ro = {"id": new_id("rpr"), "number": await next_doc_number("repair_orders", "number", "RPR-", entity_id=entity_id),
          "entity_id": entity_id, "kind": kind, "kind_label": KINDS[kind], **partner, "target": target,
          "lines": lines, "cost": cost, "cost_estimate": _cost_total(cost, lines), "status": "draft",
          "status_label": STATUS_LABEL["draft"], "notes": (data.get("notes") or "").strip(),
          "source_type": (data.get("source_type") or "").strip(), "source_id": (data.get("source_id") or "").strip(),
          "created_by": actor.get("name", ""), "created_by_id": actor.get("id", ""), "created_at": now_iso(),
          "updated_at": now_iso(),
          "timeline": [{"at": now_iso(), "by": actor.get("name", ""), "status": "draft",
                        "note": f"Dibuat · {len(lines)} roll · {KINDS[kind]}"}]}
    await db.repair_orders.insert_one(dict(ro))
    if ro["source_type"] and ro["source_id"]:
        from services import doc_refs_service as refs
        await refs.safe_link(("repair_order", ro["id"]), (ro["source_type"], ro["source_id"]), "parent",
                             note="Roll dikirim ke perbaikan")
    ro.pop("_id", None)
    return ro


async def get(ro_id: str) -> Dict[str, Any]:
    ro = await db.repair_orders.find_one({"id": ro_id}, {"_id": 0})
    if not ro:
        raise LookupError("Dokumen perbaikan tidak ditemukan.")
    return ro


async def _push(ro: Dict[str, Any], status: str, actor: Dict[str, Any], note: str, sets: Dict[str, Any],
                expect: str) -> Dict[str, Any]:
    res = await db.repair_orders.update_one(
        {"id": ro["id"], "status": expect},
        {"$set": {**sets, "status": status, "status_label": STATUS_LABEL[status], "updated_at": now_iso()},
         "$push": {"timeline": {"at": now_iso(), "by": actor.get("name", ""), "status": status, "note": note}}})
    if res.matched_count == 0:
        raise RepairError("Dokumen perbaikan baru saja diubah pengguna lain — muat ulang.")
    return await get(ro["id"])


async def _movement(r: Dict[str, Any], mtype: str, qty: float, ro: Dict[str, Any], note: str = "") -> None:
    await db.inventory_movements.insert_one({
        "id": new_id("mov"), "product_id": r["product_id"], "warehouse_id": r.get("warehouse_id", ""),
        "owner_entity_id": r.get("owner_entity_id", ""), "movement_type": mtype, "quantity": round(qty, 2),
        "unit": r.get("unit", "meter"), "lot": r.get("lot", ""), "roll_id": r["id"], "qty_rolls": 1,
        "source_document": ro["id"], "source_number": ro.get("number", ""), "note": note, "timestamp": now_iso()})


async def send(ro_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Roll keluar dari ATP (status `wip`, `bucket_ref` = perbaikan) — tetap persediaan milik PT (tanpa jurnal)."""
    from services.roll_service import rebuild_balance
    ro = await get(ro_id)
    if ro["status"] != "draft":
        raise RepairError("Hanya perbaikan berstatus Draf yang bisa dikirim.")
    ref = {"type": "repair", "id": ro["id"], "number": ro["number"], "partner": ro.get("partner_name", "")}
    moved, segs = [], set()
    for ln in ro["lines"]:
        res = await db.inventory_rolls.update_one(
            {"id": ln["roll_id"], "status": ln["prev_status"], "reserved_ref": {"$in": [None, ""]},
             "repair_open": {"$in": [None, ""]}},
            {"$set": {"status": REPAIR_STATUS, "bucket_ref": ref, "repair_open": ro["id"], "updated_at": now_iso()}})
        if not res.modified_count:
            for done in moved:   # kembalikan yang sudah terpindah — semua atau tidak sama sekali
                await db.inventory_rolls.update_one({"id": done["roll_id"], "repair_open": ro["id"]},
                                                    {"$set": {"status": done["prev_status"], "bucket_ref": None,
                                                              "repair_open": "", "updated_at": now_iso()}})
            raise RepairError(f"Roll {ln.get('roll_no') or ln['roll_id']} berubah sejak dokumen dibuat (dipesan/dipindah) "
                              "— keluarkan dari daftar lalu kirim lagi.")
        moved.append(ln)
    for ln in moved:
        r = await db.inventory_rolls.find_one({"id": ln["roll_id"]}, {"_id": 0})
        await _movement(r, "repair_send", ln["qty_sent"], ro, f"Kirim ke {ro.get('partner_name', '')}")
        segs.add((r["product_id"], r["warehouse_id"], r["owner_entity_id"]))
    for p, w, o in segs:
        await rebuild_balance(p, w, o)
    return await _push(ro, "sent", actor, f"Dikirim ke {ro.get('partner_name', '')} · {len(moved)} roll keluar dari stok jual",
                       {"sent_at": now_iso(), "sent_by": actor.get("name", "")}, "draft")


async def cancel(ro_id: str, actor: Dict[str, Any], reason: str) -> Dict[str, Any]:
    from services.roll_service import rebuild_balance
    ro = await get(ro_id)
    if ro["status"] not in ("draft", "sent"):
        raise RepairError("Perbaikan yang sudah selesai/batal tidak bisa dibatalkan.")
    if len((reason or "").strip()) < 5:
        raise RepairError("Alasan batal wajib (minimal 5 huruf).")
    segs = set()
    if ro["status"] == "sent":
        for ln in ro["lines"]:
            res = await db.inventory_rolls.update_one(
                {"id": ln["roll_id"], "repair_open": ro["id"]},
                {"$set": {"status": ln["prev_status"], "bucket_ref": None, "repair_open": "", "updated_at": now_iso()}})
            if res.modified_count:
                r = await db.inventory_rolls.find_one({"id": ln["roll_id"]}, {"_id": 0})
                await _movement(r, "repair_cancel", ln["qty_sent"], ro, "Perbaikan dibatalkan — roll kembali")
                segs.add((r["product_id"], r["warehouse_id"], r["owner_entity_id"]))
    for p, w, o in segs:
        await rebuild_balance(p, w, o)
    return await _push(ro, "cancelled", actor, f"Dibatalkan: {reason.strip()}", {"cancel_reason": reason.strip()}, ro["status"])


async def receive(ro_id: str, data: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Terima hasil: qty hasil per roll (susut), grade & dye lot baru; biaya (aktual atau perkiraan) DIKAPITALISASI ke
    roll hasil sebanding qty hasil. Celup ulang ke SKU lain → roll ANAK ber-SKU baru, roll induk ditutup."""
    from services.roll_service import rebuild_balance
    ro = await get(ro_id)
    if ro["status"] != "sent":
        raise RepairError("Hanya perbaikan berstatus Dikirim yang bisa diterima.")
    got = {x.get("roll_id"): x for x in data.get("lines") or []}
    if set(got) != {ln["roll_id"] for ln in ro["lines"]}:
        raise RepairError("Isi hasil untuk SEMUA roll di dokumen ini.")
    results = []
    for ln in ro["lines"]:
        x = got[ln["roll_id"]]
        q_out = round(float(x.get("qty_out") or 0), 2)
        if q_out < 0 or q_out > ln["qty_sent"] + EPS:
            raise RepairError(f"Qty hasil roll {ln.get('roll_no')} harus 0–{ln['qty_sent']}.")
        results.append({**ln, "qty_out": q_out, "shrink": round(ln["qty_sent"] - q_out, 2),
                        "grade_after": (x.get("grade") or ln.get("grade_before") or "").strip(),
                        "lot_after": (x.get("dye_lot") or ro.get("target", {}).get("dye_lot") or ln.get("lot_before") or "").strip()})
    cost = _norm_cost({**ro.get("cost", {}), **(data.get("cost") or {})}) if data.get("cost") else ro.get("cost", {})
    total_cost = round(float(data["actual_cost"]), 2) if data.get("actual_cost") not in (None, "") else _cost_total(cost, results)
    if total_cost < 0:
        raise RepairError("Biaya aktual tidak boleh negatif.")
    sum_out = sum(r["qty_out"] for r in results)
    target_pid = (ro.get("target") or {}).get("product_id") or ""
    segs = set()
    for r in results:
        roll = await db.inventory_rolls.find_one({"id": r["roll_id"], "repair_open": ro["id"]}, {"_id": 0})
        if not roll:
            raise RepairError(f"Roll {r.get('roll_no')} tidak lagi tercatat di perbaikan ini.")
        old_val = float(roll.get("length_remaining") or 0) * float(roll.get("unit_cost") or roll.get("base_unit_cost") or 0)
        alloc = round(total_cost * r["qty_out"] / sum_out, 2) if sum_out > EPS else 0.0
        new_uc = round((old_val + alloc) / r["qty_out"], 4) if r["qty_out"] > EPS else 0.0
        r.update({"cost_allocated": alloc, "unit_cost_after": new_uc, "value_before": round(old_val, 2)})
        hist = {"order_id": ro["id"], "number": ro["number"], "kind": ro["kind"], "at": now_iso(),
                "qty_before": r["qty_sent"], "qty_after": r["qty_out"], "grade_before": r.get("grade_before", ""),
                "grade_after": r["grade_after"], "lot_before": r.get("lot_before", ""), "lot_after": r["lot_after"],
                "cost_allocated": alloc}
        segs.add((roll["product_id"], roll["warehouse_id"], roll["owner_entity_id"]))
        if r["shrink"] > EPS:
            await _movement(roll, "repair_loss", r["shrink"], ro, "Susut perbaikan")
        if r["qty_out"] <= EPS:   # roll habis/rusak total di perbaikan
            await db.inventory_rolls.update_one({"id": roll["id"]}, {
                "$set": {"status": "consumed", "length_remaining": 0.0, "consumed_ref": ro["id"], "bucket_ref": None,
                         "repair_open": "", "updated_at": now_iso()}, "$push": {"repair_history": hist}})
            continue
        if ro["kind"] == "celup_ulang" and target_pid and target_pid != roll["product_id"]:
            child = {**roll, "id": new_id("roll"), "roll_no": f"{roll.get('roll_no') or 'ROLL'}-C",
                     "product_id": target_pid, "parent_roll_id": roll["id"], "status": "available", "bucket_ref": None,
                     "repair_open": "", "length_remaining": r["qty_out"], "length_initial": r["qty_out"],
                     "length_reserved": 0, "length_reservations": [], "reserved_ref": None,
                     "grade": r["grade_after"], "lot": r["lot_after"], "lot_id": "", "unit_cost": new_uc,
                     "base_unit_cost": new_uc, "repair_history": list(roll.get("repair_history") or []) + [hist],
                     "created_at": now_iso(), "updated_at": now_iso(), "source": "repair"}
            child.pop("_id", None)
            await db.inventory_rolls.insert_one(child)
            await db.inventory_rolls.update_one({"id": roll["id"]}, {
                "$set": {"status": "consumed", "length_remaining": 0.0, "consumed_ref": ro["id"], "bucket_ref": None,
                         "repair_open": "", "child_roll_ids": [child["id"]], "updated_at": now_iso()},
                "$push": {"repair_history": hist}})
            await _movement(child, "repair_receive", r["qty_out"], ro, f"Celup ulang → SKU {ro['target'].get('product_sku', '')}")
            r.update({"result_roll_id": child["id"], "result_roll_no": child["roll_no"], "result_product_id": target_pid})
            segs.add((target_pid, child["warehouse_id"], child["owner_entity_id"]))
        else:
            await db.inventory_rolls.update_one({"id": roll["id"]}, {
                "$set": {"status": "available", "bucket_ref": None, "repair_open": "", "length_remaining": r["qty_out"],
                         "grade": r["grade_after"], "lot": r["lot_after"], "unit_cost": new_uc, "base_unit_cost": new_uc,
                         **({"lot_id": ""} if r["lot_after"] != r.get("lot_before") else {}), "updated_at": now_iso()},
                "$push": {"repair_history": hist}})
            await _movement({**roll, "lot": r["lot_after"]}, "repair_receive", r["qty_out"], ro, "Hasil perbaikan kembali ke stok")
            r.update({"result_roll_id": roll["id"], "result_roll_no": roll.get("roll_no", ""), "result_product_id": roll["product_id"]})
    for p, w, o in segs:
        await rebuild_balance(p, w, o)
    je = None
    if total_cost > EPS:   # P7-K1 — kapitalisasi biaya: Dr Persediaan / Cr Hutang (mitra) | Overhead diserap (internal)
        from services import gl_service as gl
        await gl.seed_default_coa()
        credit = gl.ACC_HUTANG if ro.get("partner_type") == "makloon" else gl.ACC_OVERHEAD_APPLIED
        je = await gl._insert_entry(  # noqa: SLF001 — pola posting dokumen operasional (lihat post_landed_cost)
            lines=gl._balanced_pair(gl.ACC_PERSEDIAAN, credit, total_cost, f"Kapitalisasi biaya {_label(ro)}"),  # noqa: SLF001
            description=f"{_label(ro)} · {ro.get('partner_name', '')}", date=now_iso(), source_type="repair_order",
            source_id=ro["id"], entity_id=ro["entity_id"], created_by=actor.get("name", ""), source_label=ro["number"])
    total_shrink = round(sum(r["shrink"] for r in results), 2)
    return await _push(ro, "done", actor,
                       f"Diterima · hasil {round(sum_out, 2)} (susut {total_shrink}) · biaya {rupiah(total_cost)} dikapitalisasi",
                       {"lines": results, "received_at": now_iso(), "received_by": actor.get("name", ""),
                        "actual_cost": total_cost, "cost": cost, "total_shrink": total_shrink,
                        "journal_id": (je or {}).get("id", ""), "journal_number": (je or {}).get("number", "")}, "sent")


async def list_orders(entity_ids: List[str], status: str = "", q: str = "", limit: int = 200) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {"entity_id": {"$in": entity_ids}}
    if status:
        query["status"] = status
    if q.strip():
        rx = {"$regex": q.strip(), "$options": "i"}
        query["$or"] = [{"number": rx}, {"partner_name": rx}, {"lines.roll_no": rx}, {"lines.sku": rx}]
    return await db.repair_orders.find(query, {"_id": 0, "timeline": 0}).sort("created_at", -1).to_list(limit)


async def roll_repairs(roll_id: str) -> List[Dict[str, Any]]:
    return await db.repair_orders.find({"lines.roll_id": roll_id}, {"_id": 0, "id": 1, "number": 1, "kind_label": 1,
                                                                   "status_label": 1, "partner_name": 1, "created_at": 1}
                                       ).sort("created_at", -1).to_list(50)
