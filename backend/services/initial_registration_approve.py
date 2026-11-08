"""PREP-B — persetujuan massal pendaftaran awal (per produk×PT atau seluruh sesi) oleh `inventory.approve_count`.

Per kelompok (rencana `initial_registration_plan.build_plan`, angka sama dengan layar rekonsiliasi):
  1. baris yang cocok dengan roll lama → roll lama DIPAKAI ULANG (CAS + catatan operasi bertahap mesin opname:
     alamat/qty/atribut diperbarui, mutasi relokasi/penyesuaian) lalu tag ditautkan;
  2. baris lain → roll BARU `create_inbound_roll(acquired_via="initial_registration")` ber-id deterministik
     (sesi:baris), biaya rata-rata beku (K-OPN-02), tag RFID ditautkan `rfid_service.encode_tag(..., epc=...)`;
  3. roll lama tanpa pasangan → dihapus (`write_off_missing` tanpa jurnal per roll);
  4. SATU jurnal selisih per kelompok (`gl.post_cycle_count_variance`, idempoten per source_id `sesi:reg:kelompok`)
     — hanya bila kelompok tuntas (atau pengecualian diterima penyetuju).
Semua langkah idempoten → aman diulang sesudah gangguan; klaim saga sesi mencegah dua penyetuju bersamaan
(gagal di tengah: kunci dilepas supaya pengulangan MELANJUTKAN). Sesi tuntas → area "terverifikasi pendaftaran"
(`registration_area_status`) dan pembekuan dilepas.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core_utils import now_iso
from db import db
from services import initial_registration_plan as plan_svc

LINES = "initial_registration_lines"   # sama dengan initial_registration_plan.LINES
EPS = 0.001
CONFLICT = "Roll lama berubah sejak didaftarkan — periksa ulang roll ini."


def new_roll_id(session_id: str, line_id: str) -> str:
    return "roll_" + hashlib.sha1(f"{session_id}:reg:{line_id}".encode()).hexdigest()[:12]


async def _retire(tag_id: str, owner: str, reason: str) -> None:
    from services import rfid_service
    tag = await db.rfid_tags.find_one({"id": tag_id}, {"_id": 0, "status": 1, "roll_id": 1})
    if not tag:
        return
    if tag.get("status") == "active":
        try:
            await rfid_service.retire_tag(tag_id, [owner])
        except HTTPException:
            pass
    elif tag.get("status") == "pending_print":
        await db.rfid_tags.update_one({"id": tag_id, "status": "pending_print"}, {"$set": {"status": "retired", "retired_at": now_iso()}})
        await db.inventory_rolls.update_one({"id": tag.get("roll_id"), "rfid_tag_id": tag_id}, {"$set": {"rfid_tag_id": None}})
    await db.rfid_tags.update_one({"id": tag_id}, {"$set": {"retire_reason": reason}})


async def link_tag(session: Dict[str, Any], roll_id: str, line: Dict[str, Any], actor: str,
                   old_ids: set) -> Dict[str, Any]:
    """Tautkan EPC baris ke roll (idempoten). Tag hidup lain ber-EPC sama milik roll LAMA di cakupan → dicabut dulu
    (identitas fisik pindah ke hasil pendaftaran); milik roll lain → pengecualian."""
    from services import rfid_service
    owner, epc = line.get("owner_entity_id") or "", line["epc"]
    roll = await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0, "rfid_tag_id": 1})
    if (roll or {}).get("rfid_tag_id"):
        cur = await db.rfid_tags.find_one({"id": roll["rfid_tag_id"]}, {"_id": 0, "id": 1, "epc": 1, "status": 1})
        if cur and cur.get("epc") == epc and cur.get("status") in ("active", "pending_print"):
            return {"ok": True, "tag_id": cur["id"]}
        await _retire(roll["rfid_tag_id"], owner, "diganti tag pendaftaran awal")
    clash = await db.rfid_tags.find_one({"epc": epc, "status": {"$in": ["active", "pending_print"]}}, {"_id": 0, "id": 1, "roll_id": 1})
    if clash and clash.get("roll_id") != roll_id:
        if clash.get("roll_id") not in old_ids:
            return {"ok": False, "message": f"EPC {line.get('epc_display') or epc} dipakai tag aktif roll lain di luar cakupan."}
        await _retire(clash["id"], owner, "tag lama pindah ke roll hasil pendaftaran awal")
    status = "pending_print" if line.get("tag_state") == "pending_write" else "active"
    try:
        tag = await rfid_service.encode_tag(roll_id, [owner], epc=epc, actor_name=actor, status=status)
    except HTTPException as exc:
        return {"ok": False, "message": f"Tag gagal ditautkan: {exc.detail}"}
    await db.inventory_rolls.update_one({"id": roll_id}, {"$set": {"rfid_epc": epc}})
    return {"ok": True, "tag_id": tag["id"]}


def _roll_stamp(session: Dict[str, Any], line: Dict[str, Any], actor: str) -> Dict[str, Any]:
    return {"length_verified": bool(line.get("length_verified")), "grade": line.get("grade") or "A",
            "registration": {"session_id": session["id"], "line_id": line["id"], "at": now_iso(), "by": actor,
                             "old_roll_no": line.get("old_roll_no", ""), "lot": line.get("lot", ""),
                             "length_source": "label" if line.get("length_verified") else "belum_terverifikasi"},
            "updated_at": now_iso()}


async def _reuse(session: Dict[str, Any], line: Dict[str, Any], old: Dict[str, Any], actor: str) -> Dict[str, Any]:
    from services import stock_count_roll_service as rcs
    key, ref = f"reg_{old['id']}", f"{session['id']}:reg:{old['id']}"
    out = await rcs.resume_roll_op(session, key, CONFLICT)
    if out is None:
        cas = {"warehouse_id": session["warehouse_id"], "bin_id": old.get("bin_id"), "length_remaining": old["length_remaining"]}
        live = await db.inventory_rolls.find_one({"id": old["id"], **cas}, {"_id": 0, "id": 1, "active_movement": 1, "length_reserved": 1})
        new_qty = round(float(line["qty"]), 4)
        if not live:
            return {"status": "recount", "message": CONFLICT}
        if (live.get("active_movement") or {}).get("id"):
            return {"status": "exception", "message": "Roll lama sedang dalam perpindahan berjalan — selesaikan dulu."}
        if float(live.get("length_reserved") or 0) > new_qty + EPS:
            return {"status": "exception", "message": "Panjang terdaftar lebih kecil dari reservasi potong roll lama."}
        diff = round(new_qty - float(old["length_remaining"]), 4)
        upd = {**_roll_stamp(session, line, actor), "bin_id": line["bin_id"], "bin_code": line.get("bin_code", ""),
               "length_remaining": new_qty, **({"dye_lot": line["dye_lot"]} if line.get("dye_lot") else {})}
        moves = []
        if line["bin_id"] != old.get("bin_id"):
            moves.append({"qty": 0.0, "type": "cycle_count_relocation", "extra": {"from_bin_id": old.get("bin_id"), "to_bin_id": line["bin_id"]}})
        if abs(diff) > EPS:
            moves.append({"qty": diff, "type": "cycle_count_adjustment", "extra": {}})
        roll = {k: old.get(k) for k in rcs.ROLL_FIELDS if k != "_id"}
        result = {"status": "applied", "roll_id": old["id"], "roll_no": old.get("roll_no"), "reused": True,
                  "old_qty": float(old["length_remaining"]), "qty": new_qty, "qty_diff": diff,
                  "value": round(diff * plan_svc._cost(old), 2), "at": now_iso(), "by": actor}
        out = await rcs.start_roll_op(session, key, cas, upd,
                                      {"ref": ref, "roll": roll, "movements": moves, "journal": None,
                                       "rebuild": abs(diff) > EPS, "result": result}, CONFLICT)
    return out


async def _create(session: Dict[str, Any], line: Dict[str, Any], cost: float, actor: str) -> Dict[str, Any]:
    from services.roll_service import create_inbound_roll
    rid = new_roll_id(session["id"], line["id"])
    roll = await create_inbound_roll(
        line["product_id"], session["warehouse_id"], line["owner_entity_id"], round(float(line["qty"]), 4), roll_id=rid,
        bin_id=line["bin_id"], acquired_via="initial_registration", ref_id=session["id"], created_by=actor, unit_cost=cost,
        lot=line.get("lot") or f"REG-{session['id'][-8:].upper()}", dye_lot=line.get("dye_lot") or "", lot_source="adjustment",
        lot_source_ref={"type": "initial_registration", "session_id": session["id"], "line_id": line["id"]})
    await db.inventory_rolls.update_one({"id": rid}, {"$set": {**_roll_stamp(session, line, actor),
                                                               "bin_code": line.get("bin_code", "")}})
    return {"status": "applied", "roll_id": rid, "roll_no": roll.get("roll_no"), "reused": False,
            "qty": float(line["qty"]), "unit_cost": cost, "value": round(float(line["qty"]) * cost, 2),
            "at": now_iso(), "by": actor}


async def apply_group(session: Dict[str, Any], g: Dict[str, Any], actor: str, accept_exceptions: bool) -> Dict[str, Any]:
    from services import gl_service as gl
    from services import stock_count_roll_service as rcs
    from services.roll_service import rebuild_balance
    sid = session["id"]
    old_ids = {r["id"] for r in g["old"]}
    lines_out: List[Dict[str, Any]] = []
    exceptions: List[Dict[str, Any]] = []
    for ln in g["lines"]:
        if ln.get("status") == "applied":
            lines_out.append(ln.get("result") or {})
            continue
        r = await (_reuse(session, ln, ln["reuse_roll"], actor) if ln.get("reuse_roll")
                   else _create(session, ln, float(g["unit_cost"] or 0), actor))
        if r.get("status") == "applied":
            t = await link_tag(session, r["roll_id"], ln, actor, old_ids)
            r = {**r, "tag_id": t.get("tag_id")} if t["ok"] else {**r, "status": "exception", "message": t["message"]}
        if r.get("status") != "applied":
            exceptions.append({"line_id": ln["id"], "epc": ln.get("epc_display"), "message": r.get("message")})
            continue
        await db[LINES].update_one({"id": ln["id"], "status": "draft"},
                                   {"$set": {"status": "applied", "live": False, "result": r, "applied_at": now_iso()},
                                    "$unset": {"match_key": ""}})
        lines_out.append(r)
    wos = dict((session.get("registration") or {}).get("writeoffs") or {})
    for e in g["missing"]:
        if e["id"] in wos:
            continue
        adj = await rcs.write_off_missing(session, {"roll_id": e["id"], "bin_id": e.get("bin_id"), "qty": float(e["length_remaining"])},
                                          actor, post_journal=False, label="tak terdaftar")
        if adj.get("status") != "applied":
            exceptions.append({"roll_id": e["id"], "roll_no": e.get("roll_no"), "message": adj.get("message")})
            continue
        if e.get("rfid_tag_id"):
            await _retire(e["rfid_tag_id"], e.get("owner_entity_id") or "", "roll lama tidak terdaftar ulang (pendaftaran awal)")
        wos[e["id"]] = {"written_off": adj.get("written_off"), "value": adj.get("value"), "roll_no": e.get("roll_no"), "at": now_iso()}
        await db.cycle_count_sessions.update_one({"id": sid}, {"$set": {f"registration.writeoffs.{e['id']}": wos[e["id"]]}})
    value = round(sum(float(x.get("value") or 0) for x in lines_out)
                  + sum(float(wos[e["id"]].get("value") or 0) for e in g["missing"] if e["id"] in wos), 2)
    res: Dict[str, Any] = {"status": "exception" if exceptions else "applied", "exceptions": exceptions, "value": value,
                           "new_rolls": sum(1 for x in lines_out if not x.get("reused")),
                           "reused_rolls": sum(1 for x in lines_out if x.get("reused")),
                           "written_off": sum(1 for e in g["missing"] if e["id"] in wos), "journal_id": None, "at": now_iso(), "by": actor}
    if not exceptions or accept_exceptions:
        src = f"{sid}:reg:{g['key']}"
        je = await gl.post_cycle_count_variance(source_id=src, entity_id=g["owner_entity_id"], amount_signed=value,
                                                label=f"Pendaftaran awal {session.get('number') or session.get('name')} · {g['sku']}")
        if not je:
            je = await db.journal_entries.find_one({"source_type": "cycle_count_variance", "source_id": src,
                                                    "status": {"$ne": "void"}}, {"_id": 0, "id": 1})
        res.update({"journal_id": (je or {}).get("id"), "status": "applied" if not exceptions else "accepted_with_exceptions"})
    await rebuild_balance(g["product_id"], session["warehouse_id"], g["owner_entity_id"])
    return res


async def approve(session: Dict[str, Any], keys: List[str], actor: str, allowed: Optional[List[str]], *,
                  reason: str, zero_cost_reason: str, accept_exceptions: bool) -> Dict[str, Any]:
    from services import atomic_claim as _saga
    from services.initial_registration_service import assert_status, load
    assert_status(session, "pending_approval")
    plan = await plan_svc.build_plan(session)
    by_key = {g["key"]: g for g in plan["groups"]}
    stray = sorted(set(keys) - set(by_key))
    if stray:
        raise HTTPException(status_code=400, detail="Kelompok produk tidak ada di rekonsiliasi: " + ", ".join(stray[:5]))
    done = lambda g: (g.get("result") or {}).get("status") in ("applied", "accepted_with_exceptions")  # noqa: E731
    todo = [g for g in (by_key[k] for k in keys) if not done(g)] if keys else [g for g in plan["groups"] if not done(g)]
    plan_svc.assert_owner_access(todo, allowed)
    for g in todo:
        if g["new"] and g["unit_cost"] <= 0 and not zero_cost_reason:
            raise HTTPException(status_code=400, detail=f"{g['sku']}: tidak ada biaya rata-rata acuan — isi alasan biaya nol.")
    if not keys and plan["unmapped"]:
        raise HTTPException(status_code=400, detail=f"{len(plan['unmapped'])} baris 'produk belum dikenali' — petakan ke produk "
                            "atau batalkan barisnya sebelum seluruh sesi disetujui.")
    await _saga.claim("cycle_count_sessions", session["id"], "initial_registration_approve",
                      precondition={"status": "pending_approval"}, actor=actor)
    try:
        sess = await load(session["id"])
        # Rencana dibaca ULANG sesudah klaim: persetujuan lain yang selesai di antara baca & klaim tidak diulang.
        fresh = {g["key"]: g for g in (await plan_svc.build_plan(sess))["groups"]}
        todo = [fresh[g["key"]] for g in todo if g["key"] in fresh and not done(fresh[g["key"]])]
        missing_costs = {g["key"]: {"cost": g["unit_cost"], "basis": g["cost_basis"], "at": now_iso()}
                         for g in todo if g["new"] and g["key"] not in (sess["registration"].get("costs") or {})}
        if missing_costs:
            await db.cycle_count_sessions.update_one({"id": session["id"]}, {"$set": {
                **{f"registration.costs.{k}": v for k, v in missing_costs.items()}}})
        results = {}
        for g in todo:
            results[g["key"]] = await apply_group(await load(session["id"]), g, actor, accept_exceptions)
            await db.cycle_count_sessions.update_one({"id": session["id"]}, {"$set": {f"registration.groups.{g['key']}": results[g["key"]]}})
        after = await plan_svc.build_plan(await load(session["id"]))
        complete = not after["unmapped"] and all(done(g) for g in after["groups"])
        final: Dict[str, Any] = {"updated_at": now_iso(), "registration.last_approval": {"by": actor, "at": now_iso(), "reason": reason,
                                                                                      "zero_cost_reason": zero_cost_reason}}
        if complete:
            exc = any((g.get("result") or {}).get("status") == "accepted_with_exceptions" for g in after["groups"])
            final.update({"status": "approved_with_exceptions" if exc else "approved", "approved_by": actor,
                          "approved_at": now_iso(), "approval_reason": reason, "freeze.active": False,
                          "freeze.released_at": now_iso(), "registration.verified_at": now_iso()})
            await mark_verified(sess)
    except Exception:
        await _saga.release("cycle_count_sessions", session["id"])
        raise
    await db.cycle_count_sessions.update_one({"id": session["id"]}, _saga.finish_set(final))
    return {"results": results, "complete": complete, "session": await load(session["id"])}


async def mark_verified(session: Dict[str, Any]) -> None:
    """Area cakupan → 'terverifikasi pendaftaran' (tanggal) — dibaca cutover/gate (`registration_freeze.area_verification`)."""
    reg = session.get("registration") or {}
    nodes = reg.get("node_ids") or ["*"]
    labels = reg.get("node_labels") or ["Seluruh gedung"]
    for i, nid in enumerate(nodes):
        key = f"{session['warehouse_id']}:{nid}"
        await db.registration_area_status.update_one({"key": key}, {"$set": {
            "key": key, "warehouse_id": session["warehouse_id"], "node_id": nid, "label": labels[i] if i < len(labels) else nid,
            "verified_at": now_iso(), "session_id": session["id"], "session_number": session.get("number", "")}}, upsert=True)
