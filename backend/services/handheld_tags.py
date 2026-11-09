"""PREP-G — EPC dibuat sistem lalu DITULIS ke tag oleh C72 (K-OPN-05: EPC bawaan tag dianggap TIDAK unik).

Tiga jalur, semuanya memakai mekanisme EPC yang ada (`rfid_service.generate_epc` 24-hex berawalan E2, keunikan terhadap
tag hidup & baris Daftar Awal hidup) — tidak ada format EPC baru:

1. **Tulis tag roll yang sudah ada** (ganti tag rusak/EPC kembar, roll potongan, roll "Belum Tag"):
   `create_write` → niat tulis `pending` ber-EPC baru (tag lama TETAP berlaku) → perangkat menulis + baca ulang →
   `confirm_write` (EPC terbaca == EPC niat) → tag lama di-retire (`rfid_service.retire_tag`) dan tag baru aktif
   (`rfid_service.encode_tag`), bukti verifikasi diikat ke tag baru. Gagal → `fail_write`; EPC niat tidak terpakai.
2. **Daftar Awal mode EPC sistem — cadangan EPC per perangkat** (`reserve_epcs`): perangkat menyimpan cadangan EPC
   sehingga bisa menulis tag & mengisi baris saat OFFLINE; baris disinkron lewat batch `registration` membawa EPC
   cadangan + `written` → `initial_registration_lines.add_line` (kait `_reserved_system_epc`) + `mark_written`.
3. **Daftar Awal mode EPC bawaan** (`read`): EPC terbaca (RSSI terkuat) dikirim apa adanya; keunikan dicek layanan asal.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from core_utils import new_id, now_iso, safe_doc
from db import db
from dependencies import audit
from services.handheld_core import HandheldCtx, assert_operator, err
from services.handheld_sync import _detail, _item, _summary, once

WRITES = "handheld_tag_writes"
POOL = "handheld_epc_reservations"
LIVE_TAG = ("active", "pending_print")
WRITE_TTL_H = 24
_IDX = {"ok": False}


async def ensure_indexes() -> None:
    if _IDX["ok"]:
        return
    await db[POOL].create_index("epc", name="uq_hh_pool_epc", unique=True)
    await db[POOL].create_index([("device_id", 1), ("session_id", 1), ("status", 1)], name="hh_pool_dev")
    await db[WRITES].create_index("epc", name="uq_hh_write_epc", unique=True)
    await db[WRITES].create_index([("roll_id", 1), ("status", 1)], name="hh_write_roll")
    _IDX["ok"] = True


async def epc_free(epc: str) -> bool:
    """EPC belum PERNAH terbit (tag status apa pun — FIX-3b RFID-2: EPC pensiun tidak dipakai ulang), baris Daftar
    Awal hidup, cadangan perangkat, atau niat tulis mana pun."""
    if await db.rfid_tags.find_one({"epc": epc}, {"_id": 1}):
        return False
    if await db.initial_registration_lines.find_one({"epc": epc, "live": True}, {"_id": 1}):
        return False
    return not (await db[POOL].find_one({"epc": epc}, {"_id": 1}) or await db[WRITES].find_one({"epc": epc}, {"_id": 1}))


async def new_epc() -> str:
    from services.rfid_service import generate_epc
    for _ in range(8):
        e = generate_epc()
        if await epc_free(e):
            return e
    raise err(503, "EPC_GENERATION_FAILED", "Gagal membuat EPC unik — coba lagi.", retryable=True)


# ─── 1. Tulis tag roll yang sudah ada ────────────────────────────────────────
async def _roll_by_code(ctx: HandheldCtx, code: str) -> Dict[str, Any]:
    from services.epc import try_canonical
    c = (code or "").strip()
    if not c:
        raise err(400, "CODE_REQUIRED", "Pindai label/tag roll atau isi nomor roll.")
    tag = await db.rfid_tags.find_one({"epc": try_canonical(c) or c.upper(), "status": "active"}, {"_id": 0, "roll_id": 1})
    q = {"id": tag["roll_id"]} if tag else {"$or": [{"id": c}, {"roll_no": c}, {"roll_no": c.upper()}]}
    roll = await db.inventory_rolls.find_one(q, {"_id": 0})
    if not roll or roll.get("owner_entity_id") not in ctx.entity_ids:
        raise err(404, "ROLL_NOT_FOUND", "Roll tidak ditemukan di PT Anda.")
    ctx.assert_warehouse(roll.get("warehouse_id"), "roll ini")
    return roll


def _write_view(w: Dict[str, Any]) -> Dict[str, Any]:
    return {k: w.get(k) for k in ("id", "status", "purpose", "roll_id", "roll_no", "sku", "product_name", "warehouse_id", "epc",
                                  "old_epc", "old_tag_id", "expires_at", "created_at", "confirmed_at", "failed_reason")}


async def create_write(ctx: HandheldCtx, body: Dict[str, Any]) -> Dict[str, Any]:
    from services.rfid_service import PHYSICAL_STATUSES
    await ensure_indexes()
    await assert_operator(ctx, body.get("operator_session_id"), body.get("user_id"))

    async def run() -> Dict[str, Any]:
        roll = await _roll_by_code(ctx, str(body.get("roll_id") or body.get("code") or ""))
        if roll.get("status") not in PHYSICAL_STATUSES or float(roll.get("length_remaining") or 0) <= 0:
            raise err(409, "ROLL_NOT_PHYSICAL", f"Roll {roll.get('roll_no')} berstatus {roll.get('status')} — tidak bisa diberi tag.")
        mv = (roll.get("active_movement") or {}).get("id")
        if mv:
            raise err(409, "ROLL_MOVING", f"Roll {roll.get('roll_no')} sedang dalam perpindahan — selesaikan dulu sebelum ganti tag.")
        old = await db.rfid_tags.find_one({"id": roll.get("rfid_tag_id"), "status": {"$in": list(LIVE_TAG)}}, {"_id": 0}) \
            if roll.get("rfid_tag_id") else None
        pending = await db[WRITES].find_one({"roll_id": roll["id"], "status": "pending"}, {"_id": 0})
        if pending and pending.get("device_id") != ctx.device["id"]:
            raise err(409, "WRITE_IN_PROGRESS", f"Roll {roll.get('roll_no')} sedang ditulis tagnya oleh perangkat lain "
                                                f"({pending.get('device_code')}) — batalkan di perangkat itu dulu.")
        if pending:   # perangkat yang sama minta lagi (layar dibuka ulang) → niat yang sama, EPC sama
            return {"status": "accepted", "write": _write_view(pending), "reused": True}
        p = await db.products.find_one({"id": roll.get("product_id")}, {"_id": 0, "sku": 1, "name": 1}) or {}
        now = datetime.now(timezone.utc)
        w = {"id": new_id("hhw"), "status": "pending", "purpose": "replace" if old else "new", "reason": str(body.get("reason") or "")[:300],
             "roll_id": roll["id"], "roll_no": roll.get("roll_no"), "sku": p.get("sku"), "product_name": p.get("name"),
             "warehouse_id": roll.get("warehouse_id"), "owner_entity_id": roll.get("owner_entity_id"),
             "old_tag_id": (old or {}).get("id"), "old_epc": (old or {}).get("epc"), "epc": await new_epc(),
             "device_id": ctx.device["id"], "device_code": ctx.device.get("code"), "user_id": ctx.user["id"],
             "user_name": ctx.actor_name, "created_at": now.isoformat(),
             "expires_at": (now + timedelta(hours=WRITE_TTL_H)).isoformat()}
        try:
            await db[WRITES].insert_one(dict(w))
        except DuplicateKeyError as exc:
            raise err(503, "EPC_GENERATION_FAILED", "EPC bentrok — coba lagi.", retryable=True) from exc
        return {"status": "accepted", "write": _write_view(w), "reused": False}

    return await once(ctx, "tag-write", body.get("client_request_id", ""),
                      {"code": body.get("code"), "roll_id": body.get("roll_id")}, run, {"type": "tag_write"})


async def _write_doc(ctx: HandheldCtx, write_id: str) -> Dict[str, Any]:
    w = await db[WRITES].find_one({"id": write_id}, {"_id": 0})
    if not w or w.get("owner_entity_id") not in ctx.entity_ids:
        raise err(404, "WRITE_NOT_FOUND", "Niat tulis tag tidak ditemukan.")
    if w.get("device_id") != ctx.device["id"]:
        raise err(409, "WRITE_OTHER_DEVICE", "Niat tulis ini milik perangkat lain.")
    return w


async def confirm_write(ctx: HandheldCtx, write_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    from services import rfid_service as rfid
    from services.epc import try_canonical
    await assert_operator(ctx, body.get("operator_session_id"), body.get("user_id"))
    verified = try_canonical(body.get("verified_epc"))

    async def run() -> Dict[str, Any]:
        w = await _write_doc(ctx, write_id)
        if w["status"] == "confirmed":
            return {"status": "accepted", "write": _write_view(w), "already_confirmed": True}
        if w["status"] != "pending":
            raise err(409, "WRITE_CLOSED", f"Niat tulis berstatus {w['status']} — buat niat baru.")
        if verified != w["epc"]:
            raise err(409, "VERIFY_MISMATCH", "EPC hasil baca ulang tidak sama dengan EPC yang harus ditulis — tulis ulang.",
                      expected=w["epc"], verified=verified)
        roll = await db.inventory_rolls.find_one({"id": w["roll_id"]}, {"_id": 0})
        cur_tag = (roll or {}).get("rfid_tag_id")
        if (cur_tag or None) != (w.get("old_tag_id") or None):
            raise err(409, "ROLL_TAG_CHANGED", "Tag roll berubah sejak niat tulis dibuat — buat niat baru.")
        old = None
        if w.get("old_tag_id"):
            old = await db.rfid_tags.find_one({"id": w["old_tag_id"]}, {"_id": 0})
            if old and old.get("status") == "active":
                await rfid.retire_tag(old["id"], ctx.entity_ids)
            elif old and old.get("status") == "pending_print":   # tag lahir dari print job/daftar awal yang tak jadi ditulis
                await db.rfid_tags.update_one({"id": old["id"], "status": "pending_print"},
                                              {"$set": {"status": "retired", "retired_at": now_iso()}})
                await db.inventory_rolls.update_one({"id": w["roll_id"], "rfid_tag_id": old["id"]},
                                                    {"$set": {"rfid_tag_id": None, "tracking_mode": "barcode"}})
        try:
            tag = await rfid.encode_tag(w["roll_id"], ctx.entity_ids, w["epc"], ctx.actor_name, status="active")
        except HTTPException:
            if old and old.get("status") == "active":   # kompensasi: tag lama dipulihkan bila tag baru gagal lahir
                await db.rfid_tags.update_one({"id": old["id"], "status": "retired"},
                                              {"$set": {"status": "active"}, "$unset": {"retired_at": ""}})
                await db.inventory_rolls.update_one({"id": w["roll_id"], "rfid_tag_id": None},
                                                    {"$set": {"rfid_tag_id": old["id"], "tracking_mode": "rfid"}})
            raise
        now = now_iso()
        await db.rfid_tags.update_one({"id": tag["id"]}, {"$set": {"written_by_device_id": ctx.device["id"],
                                                                   "written_via": "handheld_c72", "write_id": write_id}})
        # Baca ulang C72 = bukti EPC chip yang menempel di roll (operator menempel dulu, lalu menulis).
        await db.inventory_rolls.update_one({"id": w["roll_id"], "rfid_tag_id": tag["id"]},
                                            {"$set": {"journey.verified_tag_id": tag["id"], "journey.verified_at": now}})
        await db[WRITES].update_one({"id": write_id, "status": "pending"}, {"$set": {
            "status": "confirmed", "confirmed_at": now, "tag_id": tag["id"],
            "verify": {k: body.get(k) for k in ("verified_epc", "tid", "rssi", "attempts", "write_power_dbm")}}})
        await audit(ctx.actor_name, "rfid_tag_written_handheld", "rfid_tag", tag["id"],
                    {"roll_no": w.get("roll_no"), "epc": w["epc"], "old_epc": w.get("old_epc"), "purpose": w.get("purpose")},
                    source=ctx.source)
        return {"status": "accepted", "write": _write_view(await _write_doc(ctx, write_id)), "tag_id": tag["id"]}

    return await once(ctx, "tag-confirm", body.get("client_request_id", ""), {"write_id": write_id, "verified": verified}, run,
                      {"type": "tag_confirm", "doc_id": write_id})


async def fail_write(ctx: HandheldCtx, write_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    w = await _write_doc(ctx, write_id)
    if w["status"] != "pending":
        return {"status": "accepted", "write": _write_view(w), "unchanged": True}
    await db[WRITES].update_one({"id": write_id, "status": "pending"}, {"$set": {
        "status": "failed", "failed_at": now_iso(), "failed_reason": str(body.get("reason") or "gagal tulis")[:300],
        "attempts": body.get("attempts")}})
    return {"status": "accepted", "write": _write_view(await _write_doc(ctx, write_id))}


# ─── 2/3. Daftar Awal ─────────────────────────────────────────────────────────
async def reserve_epcs(ctx: HandheldCtx, session_id: str, count: int) -> Dict[str, Any]:
    from services import handheld_tasks as tasks
    await ensure_indexes()
    s = await tasks.registration_session(ctx, session_id)
    if (s.get("registration") or {}).get("epc_mode") != "system":
        raise err(400, "EPC_MODE_READ", "Sesi ini memakai EPC bawaan tag (dibaca) — cadangan EPC tidak diperlukan.")
    if s.get("status") != "running":
        raise err(409, "DOC_CLOSED", "Sesi Daftar Awal tidak sedang berjalan.")
    have = await db[POOL].count_documents({"device_id": ctx.device["id"], "session_id": session_id, "status": "reserved"})
    want = max(0, min(int(count or 0), 200) - have)
    for _ in range(want):
        try:
            await db[POOL].insert_one({"epc": await new_epc(), "device_id": ctx.device["id"], "device_code": ctx.device.get("code"),
                                       "session_id": session_id, "user_id": ctx.user["id"], "status": "reserved",
                                       "created_at": now_iso()})
        except DuplicateKeyError:
            continue
    rows = await db[POOL].find({"device_id": ctx.device["id"], "session_id": session_id, "status": "reserved"},
                               {"_id": 0, "epc": 1}).sort("created_at", 1).to_list(400)
    return {"session_id": session_id, "epcs": [r["epc"] for r in rows], "count": len(rows), "server_time": now_iso()}


FORM_KEYS = ("product_id", "qty", "unit", "length_from_label", "lot", "dye_lot", "grade", "owner_entity_id", "bin_id",
             "old_roll_no", "note", "unrecognized", "label_raw")


async def process_lines(ctx: HandheldCtx, body: Dict[str, Any]) -> Dict[str, Any]:
    """Batch `registration`: tiap baris = satu roll fisik + tag. Hasil per baris (`client_line_id`)."""
    from services import handheld_tasks as tasks
    from services import initial_registration_lines as irl
    from services import initial_registration_service as irs
    from services.epc import try_canonical
    await ensure_indexes()
    s = await tasks.registration_session(ctx, body.get("doc_id", ""))
    if s.get("status") != "running":
        return {"status": "conflict", "error": {"code": "DOC_CLOSED", "http_status": 409,
                                                "message": f"Sesi Daftar Awal berstatus {irs.STATUS_LABEL.get(s.get('status'), s.get('status'))} — baris tidak disimpan."},
                "items": [], "summary": {}}
    system = (s.get("registration") or {}).get("epc_mode") == "system"
    items: List[Dict[str, Any]] = []
    for ln in (body.get("lines") or [])[:50]:
        cid = str(ln.get("client_line_id") or "")[:80]
        epc = try_canonical(ln.get("epc"))
        if not cid or not epc:
            items.append(_item(cid or "?", "invalid", "Baris wajib client_line_id & EPC 24 hex.", True))
            continue
        prior = await db.initial_registration_lines.find_one({"session_id": s["id"], "epc": epc, "live": True}, {"_id": 0})
        if prior and prior.get("hh_client_line_id") == cid:
            items.append(_item(cid, "saved", "Sudah tersimpan sebelumnya.", line_id=prior["id"], epc=epc,
                               tag_state=prior.get("tag_state"), roll_no=prior.get("matched_roll_no")))
            continue
        form = {k: ln.get(k) for k in FORM_KEYS if ln.get(k) is not None}
        if system:
            res = await db[POOL].find_one({"epc": epc}, {"_id": 0})
            if not res or res.get("device_id") != ctx.device["id"] or res.get("session_id") != s["id"]:
                items.append(_item(cid, "conflict", "EPC bukan cadangan perangkat ini untuk sesi ini — minta cadangan EPC baru.",
                                   True, epc=epc))
                continue
            if res.get("status") == "used" and res.get("client_line_id") != cid:
                items.append(_item(cid, "conflict", "EPC cadangan ini sudah dipakai baris lain.", True, epc=epc))
                continue
            form.update({"epc": epc, "_reserved_system_epc": True})
        else:
            form["epc"] = epc
        try:
            line = await irl.add_line(s, form, ctx.user, list(ctx.entity_ids))
        except HTTPException as exc:
            items.append(_item(cid, "conflict" if exc.status_code == 409 else "invalid", _detail(exc)["message"], True, epc=epc))
            continue
        await db.initial_registration_lines.update_one({"id": line["id"]}, {"$set": {
            "hh_client_line_id": cid, "hh_device_id": ctx.device["id"], "hh_captured_at": ln.get("captured_at")}})
        tag_state = line.get("tag_state")
        if system:
            await db[POOL].update_one({"epc": epc}, {"$set": {"status": "used", "line_id": line["id"], "client_line_id": cid,
                                                              "used_at": now_iso()}})
            if ln.get("written"):
                await irl.mark_written(s, [line["id"]], ctx.user)
                tag_state = "written"
        items.append(_item(cid, "saved", "Tersimpan." + (f" Roll lama {line['matched_roll_no']} dipakai ulang." if line.get("matched_roll_no") else ""),
                           line_id=line["id"], epc=epc, tag_state=tag_state, roll_no=line.get("matched_roll_no"),
                           length_verified=line.get("length_verified")))
    if any(i["result"] == "saved" for i in items):
        await audit(ctx.actor_name, "registration_lines_handheld", "cycle_count", s["id"],
                    {"saved": sum(1 for i in items if i["result"] == "saved"), "rejected": sum(1 for i in items if i["conflict"])},
                    source=ctx.source)
    return {"status": "accepted", "items": items, "summary": _summary(items)}


async def mark_written(ctx: HandheldCtx, session_id: str, line_ids: List[str]) -> Dict[str, Any]:
    from services import handheld_tasks as tasks
    from services import initial_registration_lines as irl
    s = await tasks.registration_session(ctx, session_id)
    return await irl.mark_written(s, line_ids, ctx.user)


async def lookup(ctx: HandheldCtx, code: str) -> Dict[str, Any]:
    roll = await _roll_by_code(ctx, code)
    tag = await db.rfid_tags.find_one({"id": roll.get("rfid_tag_id")}, {"_id": 0, "id": 1, "epc": 1, "status": 1}) \
        if roll.get("rfid_tag_id") else None
    p = await db.products.find_one({"id": roll.get("product_id")}, {"_id": 0, "sku": 1, "name": 1}) or {}
    pend = await db[WRITES].find_one({"roll_id": roll["id"], "status": "pending"}, {"_id": 0})
    return {"roll": {k: roll.get(k) for k in ("id", "roll_no", "status", "warehouse_id", "bin_code", "length_remaining", "unit",
                                              "lot", "grade", "owner_entity_id")},
            "warehouse_name": ctx.wh_name(roll.get("warehouse_id")), "sku": p.get("sku"), "product_name": p.get("name"),
            "tag": safe_doc(tag), "pending_write": _write_view(pend) if pend else None}


async def untagged(ctx: HandheldCtx, warehouse_id: Optional[str], limit: int = 300) -> List[Dict[str, Any]]:
    from services import rfid_service as rfid
    wid = warehouse_id or None
    if wid:
        ctx.assert_warehouse(wid, "gudang ini")
    rows = await rfid.untagged_rolls(ctx.entity_ids, wid, limit=max(1, min(int(limit or 300), 1000)))
    return [r for r in rows if r.get("warehouse_id") in ctx.warehouse_ids]
