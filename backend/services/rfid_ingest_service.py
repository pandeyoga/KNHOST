"""FASE R3 — Device Ingest API (kontrak hardware: gate Chainway UR300 / handheld /
printer RFID via middleware Kotlin).

Autentikasi: header `X-Device-Key` per device (bukan login user). Keputusan gate
kini SADAR-DOKUMEN: gate-in memvalidasi Putaway Order tujuan, gate-out memvalidasi
dokumen keluar (SO/transfer/PA). RFID tetap tidak mengubah stok — hanya mencatat
`rfid_reads` dan menjawab green/red agar middleware membunyikan lampu/alarm.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pymongo import ReturnDocument

from db import db
from core_utils import new_id, now_iso, safe_doc



def hash_device_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


async def ensure_api_key(device_id: str, regenerate: bool = False) -> Dict[str, Any]:
    """RF-12 — key hanya ditampilkan SEKALI saat terbit/rotasi; DB menyimpan hash saja."""
    dev = await db.rfid_devices.find_one({"id": device_id}, {"_id": 0})
    if not dev:
        raise HTTPException(status_code=404, detail="Device tidak ditemukan")
    if (dev.get("api_key_hash") or dev.get("api_key")) and not regenerate:
        raise HTTPException(status_code=409, detail=(
            "Device sudah punya API key. Key hanya ditampilkan sekali saat diterbitkan — "
            "gunakan rotasi (regenerate); key lama langsung tidak berlaku."))
    key = f"dk_{secrets.token_hex(16)}"
    await db.rfid_devices.update_one({"id": device_id}, {
        "$set": {"api_key_hash": hash_device_key(key), "api_key_hint": key[-4:],
                 "api_key_at": now_iso(), "key_rotation_required": False},
        "$unset": {"api_key": ""}})
    return {"device_id": device_id, "api_key": key, "api_key_hint": key[-4:], "shown_once": True}


async def migrate_plaintext_keys() -> int:
    """RF-12 — key plaintext lama → hash (idempotent). Ditandai wajib rotasi karena pernah terbuka."""
    n = 0
    async for d in db.rfid_devices.find({"api_key": {"$exists": True}}, {"_id": 0, "id": 1, "api_key": 1}):
        key = d.get("api_key") or ""
        upd: Dict[str, Any] = {"$unset": {"api_key": ""}}
        if key:
            upd["$set"] = {"api_key_hash": hash_device_key(key), "api_key_hint": key[-4:],
                           "key_rotation_required": True}
        await db.rfid_devices.update_one({"id": d["id"]}, upd)
        n += 1
    return n


async def authenticate(device_key: Optional[str]) -> Dict[str, Any]:
    if not device_key:
        raise HTTPException(status_code=401, detail="Header X-Device-Key wajib")
    dev = await db.rfid_devices.find_one({"api_key_hash": hash_device_key(device_key)}, {"_id": 0})
    if not dev:
        raise HTTPException(status_code=401, detail="Device key tidak dikenal")
    if dev.get("enabled") is False:  # RF-13 — lifecycle terpisah dari health (online/offline)
        raise HTTPException(status_code=403, detail="Device dinonaktifkan — hubungi admin")
    return dev


async def _mark_online(device_id: str) -> None:
    # RF-13 — filter enabled: device yang dinonaktifkan di tengah request tidak "hidup" lagi
    await db.rfid_devices.update_one({"id": device_id, "enabled": {"$ne": False}}, {"$set": {
        "status": "online", "last_heartbeat": now_iso()}})


async def heartbeat(device: Dict[str, Any]) -> Dict[str, Any]:
    await _mark_online(device["id"])
    return {"ok": True, "device_id": device["id"], "server_time": now_iso()}


MAX_EVENTS = 500           # RF-16 — batas EKSPLISIT; lebih → 413 (pecah batch), tidak dipotong diam-diam
PASSAGE_WINDOW_S = 10      # pembacaan device dalam jendela ini = satu passage (lewat gate)
DWELL_S = 120              # tag diam: EPC sama di device sama dalam jendela ini bukan event bisnis baru


def _ts(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _normalize_events(epcs: Optional[List[str]], events: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    from services.epc import try_canonical
    raw = list(events or []) + [{"epc": e} for e in (epcs or [])]
    if len(raw) > MAX_EVENTS:
        raise HTTPException(status_code=413, detail={
            "code": "BATCH_TOO_LARGE", "max_events": MAX_EVENTS, "received": len(raw),
            "message": f"Maksimal {MAX_EVENTS} event per batch — pecah batch lalu kirim ulang (tidak ada yang diproses)."})
    out = []
    for ev in raw:
        e = str((ev or {}).get("epc") or "").strip()
        if e:
            out.append({**ev, "epc": try_canonical(e) or e.upper()})
    return out


async def _passage_for(device: Dict[str, Any], now: str) -> Dict[str, Any]:
    """Passage terbuka device (last_at dalam jendela) atau passage baru."""
    cutoff = (_ts(now) - timedelta(seconds=PASSAGE_WINDOW_S)).isoformat()
    p = await db.rfid_passages.find_one({"device_id": device["id"], "last_at": {"$gte": cutoff}},
                                        {"_id": 0}, sort=[("last_at", -1)])
    if p:
        return p
    p = {"id": new_id("rpsg"), "device_id": device["id"], "device_name": device.get("name"),
         "warehouse_id": device.get("warehouse_id"), "direction": device.get("direction"),
         "started_at": now, "last_at": now, "epcs": [], "read_ids": [], "red_count": 0, "green_count": 0,
         "info_count": 0, "verdict": "info", "acknowledged_at": None}
    await db.rfid_passages.insert_one(dict(p))
    return p


async def ingest(device: Dict[str, Any], epcs: Optional[List[str]] = None,
                 events: Optional[List[Dict[str, Any]]] = None, batch_id: Optional[str] = None,
                 source: str = "device") -> Dict[str, Any]:
    """RF-16 — batch event: observasi mentah (idempoten per event_id) terpisah dari event bisnis
    (rfid_reads, satu per EPC per passage/dwell). Keputusan gate lewat gate_evaluator (P09)."""
    from pymongo.errors import BulkWriteError
    from services import gate_evaluator as ge
    if device.get("type") not in ("gate", "fixed_reader", "handheld"):
        raise HTTPException(status_code=400, detail="Tipe device ini tidak menerima pembacaan EPC")
    evs = _normalize_events(epcs, events)
    await _mark_online(device["id"])
    now = now_iso()
    is_gate = device.get("type") == "gate"
    direction = "in" if device.get("direction") == "in" else "out"
    read_type = ("gate_in" if direction == "in" else "gate_out") if is_gate else "inventory"
    # 1) observasi mentah — replay event_id yang sama = duplikat (tidak diproses ulang)
    obs = [{"_id": f"{device['id']}:{ev['event_id']}" if ev.get("event_id") else new_id("robs"),
            "device_id": device["id"], "epc": ev["epc"], "event_id": ev.get("event_id"),
            "captured_at": ev.get("captured_at"), "antenna": ev.get("antenna"), "rssi": ev.get("rssi"),
            "batch_id": batch_id, "source": source, "received_at": now, "processed": False} for ev in evs]
    dup_ids = set()
    if obs:
        try:
            await db.rfid_observations.insert_many(obs, ordered=False)
        except BulkWriteError as bwe:
            dup_ids = {obs[e["index"]]["_id"] for e in bwe.details.get("writeErrors", []) if e.get("code") == 11000}
    if dup_ids:
        # G3 D4-RFID-01 — observasi durable BELUM berarti pipeline selesai: event sama yang dulu gagal
        # di tengah (processed=False) diproses ulang, bukan dibuang sebagai duplikat.
        unfinished = {o["_id"] async for o in db.rfid_observations.find(
            {"_id": {"$in": list(dup_ids)}, "processed": False}, {"_id": 1})}
        dup_ids -= unfinished
    fresh = list(dict.fromkeys(o["epc"] for o in obs if o["_id"] not in dup_ids))
    first_obs = {}
    for o in obs:
        if o["_id"] not in dup_ids:
            first_obs.setdefault(o["epc"], o["_id"])
    passage = await _passage_for(device, now) if is_gate else None
    dwell_cut = (_ts(now) - timedelta(seconds=DWELL_S)).isoformat()
    results, reads, exits = [], [], []
    for raw in fresh:
        # read ber-id deterministik dari observasi → pemrosesan ulang mengadopsi read yang sudah durable
        rid = f"rread_{first_obs[raw]}"
        prev = await db.rfid_reads.find_one({"id": rid}, {"_id": 0}) or await db.rfid_reads.find_one(
            {"device_id": device["id"], "epc": raw, "timestamp": {"$gte": dwell_cut}},
            {"_id": 0}, sort=[("timestamp", -1)])
        if prev and prev["id"] == rid:
            reads.append(prev)          # efek lanjutan (insiden/passage/stamp) dilengkapi di bawah
            results.append({"epc": raw, **{k: prev.get(k) for k in ("result", "code", "reason", "action")},
                            "roll_no": prev.get("roll_no"), "sku": prev.get("sku"),
                            "product_name": prev.get("product_name"), "read_id": rid})
            continue
        # G3 V3-RFID-01 — cache dwell hanya berlaku di passage YANG SAMA; passage baru wajib dievaluasi ulang
        if prev and (prev.get("passage_id") or None) == ((passage or {}).get("id") or None):
            await db.rfid_reads.update_one({"id": prev["id"]}, {"$set": {"last_observed_at": now},
                                                               "$inc": {"observation_count": 1}})
            results.append({"epc": raw, "result": prev["result"], "code": prev.get("code"), "reason": prev["reason"],
                            "action": prev.get("action"),
                            "roll_no": prev.get("roll_no"), "sku": prev.get("sku"),
                            "product_name": prev.get("product_name"), "duplicate": True, "read_id": prev["id"]})
            continue
        tag = await db.rfid_tags.find_one({"epc": raw, "status": "active"}, {"_id": 0})
        roll = await db.inventory_rolls.find_one({"id": tag["roll_id"]}, {"_id": 0}) if tag else None
        if not tag or not roll:
            decision = {"result": "red", "code": "UNKNOWN_EPC", "reason": "EPC tidak dikenal / tag tidak aktif.",
                        "action": ge.action_for("UNKNOWN_EPC")}
        elif is_gate:
            decision = await ge.evaluate(direction, device.get("warehouse_id"), roll)
        else:
            decision = {"result": "info", "code": "INVENTORY", "reason": "Pembacaan inventori (handheld/fixed reader).",
                        "action": ge.action_for("INVENTORY")}
        read = {"id": f"rread_{first_obs[raw]}", "epc": raw, "tag_id": (tag or {}).get("id"), "roll_id": (roll or {}).get("id"),
                "sku": (tag or {}).get("sku"), "product_name": (tag or {}).get("product_name"),
                "roll_no": (roll or {}).get("roll_no"), "device_id": device["id"],
                "device_name": device.get("name"), "device_type": device.get("type"), "read_type": read_type,
                "warehouse_id": device.get("warehouse_id"), "location": device.get("location"),
                "owner_entity_id": (roll or {}).get("owner_entity_id"), "result": decision["result"],
                "code": decision.get("code"), "reason": decision["reason"], "action": decision.get("action"),
                "movement": decision.get("movement"),
                "passage_id": (passage or {}).get("id"), "source": source, "observation_count": 1, "timestamp": now}
        reads.append(read)
        results.append({"epc": raw, **{k: decision.get(k) for k in ("result", "code", "reason", "action")},
                        "roll_no": read["roll_no"], "sku": read["sku"], "product_name": read["product_name"],
                        "read_id": read["id"]})
        if tag and roll:
            await db.rfid_tags.update_one({"id": tag["id"]}, {"$set": {
                "last_seen_at": now, "last_seen_device_id": device["id"],
                "last_seen_device_name": device.get("name"), "last_seen_location": device.get("location"),
                "last_seen_warehouse_id": device.get("warehouse_id")}})
            if is_gate and direction == "out":
                exits.append((roll["id"], decision))
    new_reads = []
    for r in reads:   # upsert per read: retry tidak menggandakan, hitungan passage hanya untuk yang BARU
        res = await db.rfid_reads.update_one({"id": r["id"]}, {"$setOnInsert": dict(r)}, upsert=True)
        if res.upserted_id is not None:
            new_reads.append(r)
    from services import rfid_incident_service as inc  # FASE R6 — dedupe di create_from_read
    for r in reads:
        if r["result"] == "red" and r["read_type"] in ("gate_in", "gate_out"):
            await inc.create_from_read(r)
    for roll_id, decision in exits:   # stamp SESUDAH read durable (bukan sebelumnya → REPLAY_EXIT palsu)
        await ge.stamp_exit(roll_id, decision, device, now)
    if passage:
        inc_ = {f"{k}_count": sum(1 for r in new_reads if r["result"] == k) for k in ("red", "green", "info")}
        p = await db.rfid_passages.find_one_and_update(
            {"id": passage["id"]},
            {"$set": {"last_at": now}, "$addToSet": {"epcs": {"$each": [r["epc"] for r in reads]},
                                                      "read_ids": {"$each": [r["id"] for r in reads]}},
             "$inc": inc_}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
        verdict = "red" if p["red_count"] else ("green" if p["green_count"] else "info")  # UX-01 red-dominant
        await db.rfid_passages.update_one({"id": p["id"]}, {"$set": {"verdict": verdict}})
        passage = {**p, "verdict": verdict}
    if obs:
        await db.rfid_observations.update_many({"_id": {"$in": [o["_id"] for o in obs]}}, {"$set": {"processed": True}})
    greens = sum(1 for r in results if r["result"] == "green")
    reds = sum(1 for r in results if r["result"] == "red")
    return {"device": {"id": device["id"], "code": device.get("code"), "direction": device.get("direction")},
            "accepted": len(obs) - len(dup_ids), "duplicates": len(dup_ids), "count": len(results),
            "green": greens, "red": reds, "results": results,
            "passage": {k: passage.get(k) for k in ("id", "verdict", "red_count", "green_count", "started_at", "last_at")}
            if passage else None}


async def gate_status(device_id: str, ttl_s: int = 30) -> Dict[str, Any]:
    """UX-01 — status kiosk dari SERVER: umur heartbeat, passage terakhir (red-dominant, alarm terkunci
    sampai diakui) dan TTL verdict. Klien menampilkan UNKNOWN/TAHAN bila data basi."""
    dev = await db.rfid_devices.find_one({"id": device_id}, {"_id": 0, "api_key_hash": 0, "api_key": 0})
    if not dev:
        raise HTTPException(status_code=404, detail="Device tidak ditemukan")
    now = datetime.now(timezone.utc)
    hb = dev.get("last_heartbeat")
    hb_age = int((now - _ts(hb)).total_seconds()) if hb else None
    p = await db.rfid_passages.find_one({"device_id": device_id}, {"_id": 0}, sort=[("last_at", -1)])
    latched = await db.rfid_passages.find_one({"device_id": device_id, "verdict": "red", "acknowledged_at": None},
                                              {"_id": 0}, sort=[("last_at", -1)])
    show = latched or p
    if show:
        show["reads"] = await db.rfid_reads.find({"id": {"$in": show.get("read_ids") or []}}, {"_id": 0}) \
            .sort("timestamp", 1).to_list(200)
        show["age_s"] = int((now - _ts(show["last_at"])).total_seconds())
        show["expired"] = show["age_s"] > ttl_s and show is not latched
    return {"server_time": now.isoformat(), "verdict_ttl_s": ttl_s,
            "device": {"id": dev["id"], "code": dev.get("code"), "name": dev.get("name"), "status": dev.get("status"),
                       "enabled": dev.get("enabled") is not False, "direction": dev.get("direction"),
                       "last_heartbeat": hb, "heartbeat_age_s": hb_age},
            "passage": safe_doc(show) if show else None, "latched": bool(latched)}


async def list_passages(device_id: Optional[str], warehouse_id: Optional[str], limit: int = 30,
                        before: Optional[str] = None) -> List[Dict[str, Any]]:
    """Riwayat rombongan lewat gate + siapa yang mengakui alarm & catatannya."""
    q: Dict[str, Any] = {}
    if device_id:
        q["device_id"] = device_id
    if warehouse_id:
        q["warehouse_id"] = warehouse_id
    if before:
        q["last_at"] = {"$lt": before}
    rows = await db.rfid_passages.find(q, {"_id": 0, "epcs": 0}).sort("last_at", -1).to_list(min(limit, 100))
    reads = {r["id"]: r for r in await db.rfid_reads.find(
        {"id": {"$in": [i for p in rows for i in p.get("read_ids") or []]}},
        {"_id": 0, "id": 1, "roll_no": 1, "epc": 1, "result": 1, "code": 1, "reason": 1, "action": 1}).to_list(3000)}
    for p in rows:
        p["reads"] = [reads[i] for i in p.pop("read_ids", []) or [] if i in reads]
    return [safe_doc(p) for p in rows]


async def acknowledge_passage(passage_id: str, actor: str, note: str) -> Dict[str, Any]:
    """Akui alarm (buka kunci kiosk). TIDAK menghapus/mengubah read maupun insiden sumber."""
    p = await db.rfid_passages.find_one_and_update(
        {"id": passage_id, "acknowledged_at": None},
        {"$set": {"acknowledged_at": now_iso(), "acknowledged_by": actor, "acknowledge_note": note}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not p:
        raise HTTPException(status_code=409, detail="Passage tidak ditemukan / sudah diakui")
    return safe_doc(p)


async def ingest_into_session(device: Dict[str, Any], session_id: str, epcs: List[str]) -> Dict[str, Any]:
    """RF-07 — sweep handheld/fixed reader langsung ke sesi verifikasi: bukti asal = device (tercatat)."""
    if device.get("type") not in ("handheld", "fixed_reader"):
        raise HTTPException(status_code=400, detail="Hanya handheld/fixed reader yang menyetor scan ke sesi")
    sess = await db.rfid_verify_sessions.find_one({"id": session_id}, {"_id": 0, "warehouse_id": 1})
    if sess and sess.get("warehouse_id") and sess["warehouse_id"] != device.get("warehouse_id"):
        raise HTTPException(status_code=403, detail="Sesi bukan milik gudang device ini")
    await _mark_online(device["id"])
    from services.rfid_print_service import scan_session
    return await scan_session(session_id, epcs, None, ["print_verify", "loading_check", "cycle_count"],
                              "device", device.get("name") or device["id"], device["id"],
                              device.get("name") or device.get("code"))


# ─── Printer pull (middleware ambil antrean ZPL) ────────────────────────────
LEASE_SECONDS = 300
KIND_CAPABILITY = {"rfid_tag": "rfid", "qr_label": "qr"}


def _caps(device: Dict[str, Any]) -> List[str]:
    return list(device.get("capabilities") or ["rfid", "qr"])


async def pending_jobs_for_device(device: Dict[str, Any], limit: int = 5) -> Dict[str, Any]:
    """RF-15 — pull = klaim lease atomik per job ke printer ini (attempt_id + TTL). Lease kedaluwarsa
    boleh diklaim ulang printer lain; job yang masih di-lease printer lain TIDAK ikut terkirim."""
    if device.get("type") != "printer":
        raise HTTPException(status_code=400, detail="Device bukan printer")
    kinds = [k for k, c in KIND_CAPABILITY.items() if c in _caps(device)]
    now = datetime.now(timezone.utc)
    jobs: List[Dict[str, Any]] = []
    while len(jobs) < limit:
        lease = {"device_id": device["id"], "device_name": device.get("name") or device.get("code"), "attempt_id": new_id("patt"), "claimed_at": now.isoformat(),
                 "expires_at": (now + timedelta(seconds=LEASE_SECONDS)).isoformat()}
        job = await db.rfid_print_jobs.find_one_and_update(
            {"warehouse_id": device.get("warehouse_id"), "status": "queued", "kind": {"$in": kinds},
             "id": {"$nin": [j["id"] for j in jobs]},
             "$or": [{"lease": {"$exists": False}}, {"lease.expires_at": {"$lt": now.isoformat()}},
                     {"lease.device_id": device["id"]}]},
            {"$set": {"lease": lease}, "$inc": {"print_attempts": 1}},
            sort=[("created_at", 1)], projection={"_id": 0}, return_document=ReturnDocument.AFTER)
        if not job:
            break
        jobs.append(safe_doc(job))
    return {"count": len(jobs), "jobs": jobs, "lease_seconds": LEASE_SECONDS}


async def ack_job_printed(device: Dict[str, Any], job_id: str, attempt_id: Optional[str]) -> Dict[str, Any]:
    """RF-15 — ack wajib dari printer pemilik lease aktif dengan attempt_id yang sama."""
    if device.get("type") != "printer":
        raise HTTPException(status_code=403, detail="Hanya device printer yang boleh mengakui cetak")
    job = await db.rfid_print_jobs.find_one({"id": job_id}, {"_id": 0, "items.zpl": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Print job tidak ditemukan")
    if job.get("warehouse_id") != device.get("warehouse_id"):
        raise HTTPException(status_code=403, detail="Job bukan milik gudang device ini")
    if not attempt_id:
        raise HTTPException(status_code=400, detail="attempt_id wajib (dari pull antrean)")
    if job.get("status") != "queued":
        if job.get("printed_attempt_id") == attempt_id:
            return {"ok": True, "status": job["status"], "replay": True}
        raise HTTPException(status_code=409, detail=f"Job sudah berstatus {job['status']}")
    lease = job.get("lease") or {}
    if lease.get("device_id") != device["id"] or lease.get("attempt_id") != attempt_id:
        raise HTTPException(status_code=409, detail="Lease job bukan milik printer/attempt ini")
    now = now_iso()
    if (lease.get("expires_at") or "") < now:
        raise HTTPException(status_code=409, detail="Lease job kedaluwarsa — tarik ulang antrean")
    won = await db.rfid_print_jobs.find_one_and_update(
        {"id": job_id, "status": "queued", "lease.attempt_id": attempt_id, "lease.device_id": device["id"]},
        {"$set": {"status": "printed", "printed_at": now, "printed_by_device": device["id"],
                  "printed_attempt_id": attempt_id, "printed_via": "device"}, "$unset": {"lease": ""}},
        projection={"_id": 0, "items.zpl": 0})
    if not won:
        raise HTTPException(status_code=409, detail="Job berubah bersamaan — tarik ulang antrean")
    from services.rfid_print_service import on_printed
    await on_printed(won)
    return {"ok": True, "status": "printed"}
