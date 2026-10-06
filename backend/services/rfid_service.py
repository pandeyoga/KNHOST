"""RFID service (Fase 5 — SIMULATOR).

Prinsip:
- **Roll-as-SSOT**: RFID TIDAK mengubah kuantitas stok. Encode hanya mengeset
  `inventory_rolls.rfid_tag_id` + `tracking_mode="rfid"`. Read/gate hanya
  mencatat event (`rfid_reads`) & memutakhirkan `last_seen` tag. TIDAK ada
  `$inc` ke `inventory_balances`.
- Koleksi: `rfid_tags` (tag↔roll, entity-scoped via owner_entity_id),
  `rfid_devices` (reader/gate — infra per-gudang, SHARED), `rfid_reads` (event log).
- Gate memutuskan HIJAU/MERAH berbasis status roll (kontrol keluar-masuk).
"""
import uuid
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso, safe_doc

# RF-17 — kandidat tag = SATU definisi stok fisik (roll_service) + roll yang sedang bergerak/diterima.
from services.roll_service import PHYSICAL_ROLL_STATUSES as _PHYS  # noqa: E402
PHYSICAL_STATUSES = list(_PHYS) + ["allocated", "in_transit_sales", "in_transit_transfer",
                                   "receiving"]   # FASE SL — tag dipasang saat penerimaan

DEVICE_TYPES = {"gate", "fixed_reader", "handheld", "printer"}
LIVE_TAG_STATUSES = ("active", "pending_print")  # EPC terkunci (unik) selama tag hidup


def generate_epc() -> str:
    """RF-01 — EPC-96 internal kanonik: 24 hex uppercase TANPA pemisah (sama dengan isi chip)."""
    return ("E2" + uuid.uuid4().hex[:22]).upper()


# ─── Helpers ─────────────────────────────────────────────────────────────────
async def _product_map(pids: List[str]) -> Dict[str, Dict[str, Any]]:
    return {p["id"]: p for p in await db.products.find(
        {"id": {"$in": list(set(pids))}}, {"_id": 0, "id": 1, "sku": 1, "name": 1}).to_list(2000)}


async def _bin_map(warehouse_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """bin_id → {code, path, warehouse_id} untuk rekonsiliasi lokasi."""
    from services.location_service import flatten_bins
    m: Dict[str, Dict[str, Any]] = {}
    whs = await db.warehouses.find({"id": {"$in": list(set(warehouse_ids))}}, {"_id": 0}).to_list(100)
    for wh in whs:
        for b in flatten_bins(wh):
            m[b["bin_id"]] = {"code": b.get("code"), "path": b.get("path"), "warehouse_id": wh["id"]}
    return m


async def _enrich_roll(roll: Dict[str, Any]) -> Dict[str, Any]:
    p = await db.products.find_one({"id": roll.get("product_id")}, {"_id": 0, "sku": 1, "name": 1}) or {}
    roll["sku"] = p.get("sku", "")
    roll["product_name"] = p.get("name", "")
    return roll


# ─── Tags ────────────────────────────────────────────────────────────────────
async def list_tags(scope_ids: List[str], warehouse_id: Optional[str], status: Optional[str],
                    limit: int = 1000) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"owner_entity_id": {"$in": scope_ids}}
    if warehouse_id:
        q["warehouse_id"] = warehouse_id
    if status:
        q["status"] = status
    tags = await db.rfid_tags.find(q, {"_id": 0}).sort("encoded_at", -1).to_list(limit)
    return [safe_doc(t) for t in tags]


async def untagged_rolls(scope_ids: List[str], warehouse_id: Optional[str],
                         limit: int = 500) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {
        "owner_entity_id": {"$in": scope_ids},
        "length_remaining": {"$gt": 0},
        "status": {"$in": PHYSICAL_STATUSES},
        "$or": [{"rfid_tag_id": None}, {"rfid_tag_id": {"$exists": False}}, {"rfid_tag_id": ""}],
    }
    if warehouse_id:
        q["warehouse_id"] = warehouse_id
    rolls = await db.inventory_rolls.find(
        q, {"_id": 0, "id": 1, "roll_no": 1, "product_id": 1, "warehouse_id": 1,
            "owner_entity_id": 1, "lot": 1, "length_remaining": 1, "unit": 1, "status": 1, "bin_id": 1}
    ).to_list(limit)
    pm = await _product_map([r["product_id"] for r in rolls])
    for r in rolls:
        p = pm.get(r["product_id"], {})
        r["sku"] = p.get("sku", "")
        r["product_name"] = p.get("name", "")
    return rolls


async def encode_tag(roll_id: str, scope_ids: List[str], epc: Optional[str] = None,
                     actor_name: str = "System", status: str = "active") -> Dict[str, Any]:
    """`status="pending_print"` (RF-14) — tag lahir dari print job; aktif baru saat printer ack."""
    roll = await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0})
    if not roll:
        raise HTTPException(status_code=404, detail="Roll tidak ditemukan")
    if roll.get("owner_entity_id") not in scope_ids:
        raise HTTPException(status_code=403, detail="Roll di luar entitas Anda")
    if roll.get("rfid_tag_id"):
        raise HTTPException(status_code=400, detail="Roll sudah memiliki tag RFID")
    if roll.get("status") not in PHYSICAL_STATUSES or (roll.get("length_remaining") or 0) <= 0:
        raise HTTPException(status_code=400, detail="Roll tidak dalam kondisi fisik untuk di-tag")

    from services.epc import canonical_epc
    try:
        epc = canonical_epc(epc) if epc else generate_epc()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if await db.rfid_tags.find_one({"epc": epc, "status": {"$in": list(LIVE_TAG_STATUSES)}}):
        raise HTTPException(status_code=409, detail="EPC sudah dipakai tag aktif lain")
    p = await db.products.find_one({"id": roll["product_id"]}, {"_id": 0, "sku": 1, "name": 1}) or {}
    tag = {
        "id": new_id("rtag"), "epc": epc, "roll_id": roll_id,
        "product_id": roll["product_id"], "sku": p.get("sku", ""), "product_name": p.get("name", ""),
        "roll_no": roll.get("roll_no", ""), "lot": roll.get("lot", ""),
        "owner_entity_id": roll.get("owner_entity_id"), "warehouse_id": roll.get("warehouse_id"),
        "status": status,
        "last_seen_at": None, "last_seen_device_id": None, "last_seen_device_name": None,
        "last_seen_location": None, "last_seen_warehouse_id": None,
        "encoded_at": now_iso(), "encoded_by": actor_name,
    }
    from pymongo.errors import DuplicateKeyError
    try:
        await db.rfid_tags.insert_one(tag)
    except DuplicateKeyError:  # RF-01 — indeks unik EPC hidup (balapan dua encode EPC sama)
        raise HTTPException(status_code=409, detail="EPC sudah dipakai tag aktif lain")
    # Sesi 13 — CAS: roll harus MASIH tanpa tag saat ditulis; kalah → tag yang baru lahir dihapus (kompensasi).
    upd = await db.inventory_rolls.find_one_and_update(
        {"id": roll_id, "rfid_tag_id": {"$in": [None, ""]}},
        {"$set": {"rfid_tag_id": tag["id"], "tracking_mode": "rfid", "updated_at": now_iso()}}, projection={"_id": 0})
    if not upd:
        await db.rfid_tags.delete_one({"id": tag["id"]})
        raise HTTPException(status_code=409, detail={"code": "STATE_CHANGED",
                            "message": "Roll baru saja diberi tag oleh proses lain. Muat ulang daftar."})
    return safe_doc(tag)


async def auto_encode(scope_ids: List[str], warehouse_id: Optional[str],
                      actor_name: str = "System", cap: int = 200) -> Dict[str, Any]:
    rolls = await untagged_rolls(scope_ids, warehouse_id, limit=cap)
    encoded = []
    for r in rolls:
        try:
            encoded.append(await encode_tag(r["id"], scope_ids, actor_name=actor_name))
        except HTTPException:
            continue
    return {"encoded": len(encoded), "tags": encoded}


async def retire_tag(tag_id: str, scope_ids: List[str]) -> Dict[str, Any]:
    tag = await db.rfid_tags.find_one({"id": tag_id}, {"_id": 0})
    if not tag:
        raise HTTPException(status_code=404, detail="Tag tidak ditemukan")
    if tag.get("owner_entity_id") not in scope_ids:
        raise HTTPException(status_code=403, detail="Tag di luar entitas Anda")
    # G3 D4-TAG-01 — ganti identitas saat roll sedang berpindah ditolak sebelum efek
    if tag.get("roll_id"):
        moving = await db.inventory_rolls.find_one(
            {"id": tag["roll_id"], "active_movement.id": {"$exists": True}}, {"_id": 0, "active_movement": 1})
        if moving and (moving.get("active_movement") or {}).get("id"):
            mv = moving["active_movement"]
            raise HTTPException(status_code=409, detail=(
                f"Roll sedang dalam perpindahan {mv.get('number') or mv['id']} — selesaikan/batalkan dulu "
                "sebelum mengganti tag."))
    # Sesi 13 — CAS: hanya tag aktif yang bisa di-retire; kalah (sudah retired) → 409.
    won = await db.rfid_tags.find_one_and_update(
        {"id": tag_id, "status": "active"},
        {"$set": {"status": "retired", "retired_at": now_iso()}}, projection={"_id": 0})
    if not won:
        raise HTTPException(status_code=409, detail={"code": "STATE_CHANGED",
                            "message": f"Tag sudah berstatus '{tag.get('status')}' — tidak bisa di-retire dua kali."})
    if tag.get("roll_id"):
        await db.inventory_rolls.update_one(
            {"id": tag["roll_id"], "rfid_tag_id": tag_id},
            {"$set": {"rfid_tag_id": None, "tracking_mode": "barcode", "updated_at": now_iso()},
             "$unset": {"journey.verified_tag_id": ""}})  # G3 D4-TAG-01 — bukti verifikasi gugur
    return {"ok": True, "tag_id": tag_id}


# ─── Devices (SHARED infra per-gudang) ───────────────────────────────────────
DEVICE_PUBLIC_FIELDS = (
    "id", "code", "name", "type", "direction", "warehouse_id", "warehouse_name", "location",
    "status", "last_heartbeat", "created_at", "created_by", "updated_at",
    "disabled_at", "api_key_at", "api_key_hint",
)
DEVICE_SECRET_PROJECTION = {"_id": 0, "api_key": 0, "api_key_hash": 0}


def public_device(d: Dict[str, Any]) -> Dict[str, Any]:
    """RF-12 — DTO whitelist: credential/hash tidak pernah keluar lewat list/detail/update."""
    out = {k: d[k] for k in DEVICE_PUBLIC_FIELDS if k in d}
    out["enabled"] = d.get("enabled") is not False
    out["has_api_key"] = bool(d.get("api_key_hash") or d.get("api_key"))
    out["key_rotation_required"] = bool(d.get("key_rotation_required"))
    return out


async def list_devices(warehouse_id: Optional[str] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if warehouse_id:
        q["warehouse_id"] = warehouse_id
    devs = await db.rfid_devices.find(q, {"_id": 0}).sort("code", 1).to_list(500)
    return [public_device(d) for d in devs]


async def create_device(payload: Dict[str, Any], actor_name: str = "System") -> Dict[str, Any]:
    dtype = (payload.get("type") or "").strip()
    if dtype not in DEVICE_TYPES:
        raise HTTPException(status_code=400, detail=f"Tipe device tidak valid: {dtype}")
    wh = await db.warehouses.find_one({"id": payload.get("warehouse_id")}, {"_id": 0, "id": 1, "name": 1})
    if not wh:
        raise HTTPException(status_code=400, detail="Gudang tidak ditemukan")
    code = (payload.get("code") or "").strip()
    if code and await db.rfid_devices.find_one({"code": code}):
        raise HTTPException(status_code=409, detail="Kode device sudah dipakai")
    direction = payload.get("direction") or ("out" if dtype == "gate" else "n/a")
    dev = {
        "id": new_id("rdev"), "code": code or f"DEV-{uuid.uuid4().hex[:5].upper()}",
        "name": (payload.get("name") or "").strip() or "RFID Device",
        "type": dtype, "direction": direction if dtype == "gate" else "n/a",
        "warehouse_id": wh["id"], "warehouse_name": wh.get("name", ""),
        "location": (payload.get("location") or "").strip(),
        "status": payload.get("status") or "online", "enabled": True,
        "last_heartbeat": now_iso(), "created_at": now_iso(), "created_by": actor_name,
    }
    await db.rfid_devices.insert_one(dev)
    return public_device(dev)


async def update_device(device_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    dev = await db.rfid_devices.find_one({"id": device_id}, {"_id": 0})
    if not dev:
        raise HTTPException(status_code=404, detail="Device tidak ditemukan")
    allowed = {k: v for k, v in patch.items()
               if k in {"name", "status", "location", "direction", "type", "enabled"} and v is not None}
    if "type" in allowed and allowed["type"] not in DEVICE_TYPES:
        raise HTTPException(status_code=400, detail="Tipe device tidak valid")
    # RF-13 — enabled = lifecycle (revocation); status = health. Nonaktif selalu offline.
    will_enable = allowed.get("enabled", dev.get("enabled") is not False)
    if allowed.get("enabled") is False:
        allowed["status"] = "offline"
        allowed["disabled_at"] = now_iso()
    elif allowed.get("status") == "online":
        if not will_enable:
            raise HTTPException(status_code=400, detail="Device nonaktif — aktifkan dulu sebelum dinyalakan")
        allowed["last_heartbeat"] = now_iso()
    allowed["updated_at"] = now_iso()
    await db.rfid_devices.update_one({"id": device_id}, {"$set": allowed})
    return public_device(await db.rfid_devices.find_one({"id": device_id}, {"_id": 0}))


async def delete_device(device_id: str) -> Dict[str, Any]:
    res = await db.rfid_devices.delete_one({"id": device_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Device tidak ditemukan")
    return {"ok": True, "device_id": device_id}


async def seed_default_devices(actor_name: str = "System") -> Dict[str, Any]:
    """Idempotent: buat gate masuk/keluar + fixed reader untuk tiap gudang."""
    created = 0
    whs = await db.warehouses.find({}, {"_id": 0, "id": 1, "name": 1, "code": 1}).to_list(100)
    for wh in whs:
        prefix = (wh.get("code") or wh["id"]).replace("WH-", "").replace("wh_", "").upper()[:3]
        specs = [
            {"code": f"GATE-{prefix}-IN", "name": f"Gate Masuk {wh.get('name','')}", "type": "gate", "direction": "in", "location": "Dock Masuk"},
            {"code": f"GATE-{prefix}-OUT", "name": f"Gate Keluar {wh.get('name','')}", "type": "gate", "direction": "out", "location": "Dock Kirim"},
            {"code": f"RDR-{prefix}-01", "name": f"Fixed Reader {wh.get('name','')}", "type": "fixed_reader", "direction": "n/a", "location": "Zone A"},
        ]
        for s in specs:
            if await db.rfid_devices.find_one({"code": s["code"]}):
                continue
            s["warehouse_id"] = wh["id"]
            await create_device(s, actor_name)
            created += 1
    return {"created": created, "devices": await list_devices()}


# ─── Reads / Gate / Scan ─────────────────────────────────────────────────────
async def list_reads(device_id: Optional[str], result: Optional[str], read_type: Optional[str],
                     warehouse_id: Optional[str], limit: int = 100, before: Optional[str] = None,
                     scope: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = dict(scope or {})
    if device_id:
        q["device_id"] = device_id
    if result:
        q["result"] = result
    if read_type:
        q["read_type"] = {"$in": ["gate_in", "gate_out"]} if read_type == "gate" else read_type
    if before:
        q["timestamp"] = {"$lt": before}
    if warehouse_id:
        q["warehouse_id"] = warehouse_id
    reads = await db.rfid_reads.find(q, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return [safe_doc(r) for r in reads]


async def _record_read(device: Dict[str, Any], roll: Dict[str, Any], tag: Dict[str, Any],
                       read_type: str, decision: Dict[str, str]) -> Dict[str, Any]:
    read = {
        "id": new_id("rread"), "epc": tag.get("epc"), "tag_id": tag.get("id"), "roll_id": roll.get("id"),
        "sku": tag.get("sku"), "product_name": tag.get("product_name"), "roll_no": roll.get("roll_no"),
        "device_id": device["id"], "device_name": device.get("name"), "device_type": device.get("type"),
        "read_type": read_type, "warehouse_id": device.get("warehouse_id"),
        "location": device.get("location"), "owner_entity_id": roll.get("owner_entity_id"),
        "result": decision["result"], "reason": decision["reason"], "timestamp": now_iso(),
    }
    await db.rfid_reads.insert_one(read)
    if read["result"] == "red" and read_type in ("gate_in", "gate_out"):
        from services import rfid_incident_service as inc  # FASE R6 — alarm otomatis
        await inc.create_from_read(read)
    await db.rfid_tags.update_one({"id": tag["id"]}, {"$set": {
        "last_seen_at": read["timestamp"], "last_seen_device_id": device["id"],
        "last_seen_device_name": device.get("name"), "last_seen_location": device.get("location"),
        "last_seen_warehouse_id": device.get("warehouse_id"),
    }})
    return safe_doc(read)


async def gate_simulate(device_id: str, roll_id: str, scope_ids: List[str]) -> Dict[str, Any]:
    device = await db.rfid_devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Device tidak ditemukan")
    if device.get("type") != "gate":
        raise HTTPException(status_code=400, detail="Device bukan tipe gate")
    if device.get("status") != "online":
        raise HTTPException(status_code=400, detail="Gate offline — nyalakan device dulu")
    roll = await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0})
    if not roll:
        raise HTTPException(status_code=404, detail="Roll tidak ditemukan")
    if roll.get("owner_entity_id") not in scope_ids:
        raise HTTPException(status_code=403, detail="Roll di luar entitas Anda")
    tag_id = roll.get("rfid_tag_id")
    if not tag_id:
        raise HTTPException(status_code=400, detail="Roll belum ber-tag RFID — encode dulu")
    tag = await db.rfid_tags.find_one({"id": tag_id}, {"_id": 0})
    if not tag:
        raise HTTPException(status_code=404, detail="Tag RFID roll tidak ditemukan")
    if tag.get("status") != "active":
        raise HTTPException(status_code=400, detail="Tag roll tidak aktif")
    # P09 — simulator memakai jalur & evaluator yang SAMA dengan perangkat fisik (passage + dedup)
    from services.rfid_ingest_service import ingest
    res = await ingest(device, [tag["epc"]], source="simulated")
    hit = res["results"][0]
    read = await db.rfid_reads.find_one({"id": hit.get("read_id")}, {"_id": 0}) or {}
    return {**safe_doc(read), "duplicate": bool(hit.get("duplicate")), "passage": res.get("passage")}


async def reader_scan(device_id: str, scope_ids: List[str], cap: int = 60) -> Dict[str, Any]:
    device = await db.rfid_devices.find_one({"id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Device tidak ditemukan")
    if device.get("type") not in {"fixed_reader", "handheld"}:
        raise HTTPException(status_code=400, detail="Device bukan reader (pakai Gate Monitor untuk gate)")
    if device.get("status") != "online":
        raise HTTPException(status_code=400, detail="Reader offline — nyalakan device dulu")
    tags = await db.rfid_tags.find(
        {"status": "active", "warehouse_id": device.get("warehouse_id"),
         "owner_entity_id": {"$in": scope_ids}}, {"_id": 0}).to_list(cap)
    reads = []
    for tag in tags:
        roll = await db.inventory_rolls.find_one({"id": tag.get("roll_id")}, {"_id": 0})
        if not roll:
            continue
        reads.append(await _record_read(device, roll, tag, "inventory",
                                        {"result": "info", "reason": "Terbaca fixed reader (inventory sweep)."}))
    return {"scanned": len(reads), "device": safe_doc(device), "reads": reads}


# ─── Locations (rekonsiliasi last-seen vs bin) ───────────────────────────────
async def rfid_locations(scope_ids: List[str], warehouse_id: Optional[str],
                         limit: int = 1000) -> List[Dict[str, Any]]:
    tags = await list_tags(scope_ids, warehouse_id, status="active", limit=limit)
    roll_ids = [t["roll_id"] for t in tags if t.get("roll_id")]
    rolls = {r["id"]: r for r in await db.inventory_rolls.find(
        {"id": {"$in": roll_ids}}, {"_id": 0, "id": 1, "bin_id": 1, "warehouse_id": 1, "status": 1}).to_list(2000)}
    wh_ids = list({r.get("warehouse_id") for r in rolls.values() if r.get("warehouse_id")})
    binm = await _bin_map(wh_ids)
    out = []
    for t in tags:
        roll = rolls.get(t.get("roll_id"), {})
        bin_id = roll.get("bin_id")
        bin_info = binm.get(bin_id) if bin_id else None
        if not t.get("last_seen_at"):
            state, label = "unseen", "Belum terbaca"
        elif t.get("last_seen_warehouse_id") and roll.get("warehouse_id") and \
                t["last_seen_warehouse_id"] != roll["warehouse_id"]:
            state, label = "drift", "Beda gudang!"
        else:
            state, label = "tracked", "Terlacak"
        out.append({
            "tag_id": t["id"], "epc": t["epc"], "sku": t.get("sku"), "product_name": t.get("product_name"),
            "roll_no": t.get("roll_no"), "roll_status": roll.get("status"),
            "assigned_bin": (bin_info or {}).get("path") if bin_info else None,
            "assigned_bin_code": (bin_info or {}).get("code") if bin_info else None,
            "last_seen_at": t.get("last_seen_at"), "last_seen_device_name": t.get("last_seen_device_name"),
            "last_seen_location": t.get("last_seen_location"),
            "state": state, "state_label": label,
        })
    return out


# ─── Summary ─────────────────────────────────────────────────────────────────
async def rfid_summary(scope_ids: List[str], warehouse_id: Optional[str]) -> Dict[str, Any]:
    tag_q: Dict[str, Any] = {"owner_entity_id": {"$in": scope_ids}}
    if warehouse_id:
        tag_q["warehouse_id"] = warehouse_id
    tags_active = await db.rfid_tags.count_documents({**tag_q, "status": "active"})
    tags_total = await db.rfid_tags.count_documents(tag_q)
    untagged = len(await untagged_rolls(scope_ids, warehouse_id, limit=5000))

    dev_q: Dict[str, Any] = {}
    if warehouse_id:
        dev_q["warehouse_id"] = warehouse_id
    devices_total = await db.rfid_devices.count_documents(dev_q)
    devices_online = await db.rfid_devices.count_documents({**dev_q, "status": "online"})

    today = now_iso()[:10]
    read_q: Dict[str, Any] = {"timestamp": {"$gte": today}}
    if warehouse_id:
        read_q["warehouse_id"] = warehouse_id
    reads_today = await db.rfid_reads.count_documents(read_q)
    alerts_today = await db.rfid_reads.count_documents({**read_q, "result": "red"})
    return {
        "tags_total": tags_total, "tags_active": tags_active, "untagged_rolls": untagged,
        "devices_total": devices_total, "devices_online": devices_online,
        "reads_today": reads_today, "alerts_today": alerts_today,
    }


# ─── RF-01 migrasi EPC kanonik · IX-12 tag yatim ─────────────────────────────
async def migrate_epc_canonical(dry_run: bool = False) -> Dict[str, Any]:
    """EPC berpemisah/huruf kecil → kanonik di tag, sesi, job & read. Benturan (dua tag hidup
    kanonik sama) TIDAK dimigrasi — dilaporkan; indeks unik hanya dibuat bila bersih. Idempoten."""
    from services.epc import try_canonical
    live = list(LIVE_TAG_STATUSES)
    owners: Dict[str, List[str]] = {}
    plan: List[tuple] = []
    async for t in db.rfid_tags.find({}, {"_id": 0, "id": 1, "epc": 1, "status": 1}):
        c = try_canonical(t.get("epc"))
        if c and t.get("status") in live:
            owners.setdefault(c, []).append(t["id"])
        if c and c != t.get("epc"):
            plan.append((t["id"], t.get("epc"), c))
    collisions = {c: ids for c, ids in owners.items() if len(ids) > 1}
    blocked = {tid for ids in collisions.values() for tid in ids}
    todo = [p for p in plan if p[0] not in blocked]
    report = {"tags_to_migrate": len(todo), "collisions": collisions, "dry_run": dry_run}
    if dry_run:
        return report
    mapping = {old: new for _, old, new in todo}
    for tid, _old, new in todo:
        await db.rfid_tags.update_one({"id": tid}, {"$set": {"epc": new}})
    if mapping:
        await db.rfid_reads.update_many({}, [{"$set": {"epc": {"$replaceAll": {"input": {"$toUpper": {"$ifNull": ["$epc", ""]}}, "find": "-", "replacement": ""}}}}])
        async for s in db.rfid_verify_sessions.find({}, {"_id": 0, "id": 1, "expected": 1, "scanned_epcs": 1,
                                                          "missing": 1, "extra": 1}):
            fix = lambda e: mapping.get(e, try_canonical(e) or e)  # noqa: E731
            await db.rfid_verify_sessions.update_one({"id": s["id"]}, {"$set": {
                "expected": [{**e, "epc": fix(e.get("epc"))} for e in s.get("expected") or []],
                "scanned_epcs": sorted({fix(e) for e in s.get("scanned_epcs") or []}),
                "missing": [fix(e) for e in s.get("missing") or []],
                "extra": [fix(e) for e in s.get("extra") or []]}})
        async for j in db.rfid_print_jobs.find({"items.epc": {"$in": list(mapping)}}, {"_id": 0, "id": 1, "items": 1}):
            await db.rfid_print_jobs.update_one({"id": j["id"]}, {"$set": {
                "items": [{**i, "epc": mapping.get(i.get("epc"), i.get("epc"))} for i in j.get("items") or []]}})
    if not collisions:
        try:
            await db.rfid_tags.create_index("epc", name="uniq_live_epc", unique=True,
                                            partialFilterExpression={"status": {"$in": live}})
            report["unique_index"] = True
        except Exception as e:  # noqa: BLE001 — dilaporkan, bukan diam
            report["unique_index_error"] = str(e)
    return report


async def retire_orphan_tags() -> int:
    """IX-12 — retry cleanup: tag hidup yang rollnya tidak ada lagi → retired (alasan tercatat)."""
    n = 0
    async for t in db.rfid_tags.find({"status": {"$in": list(LIVE_TAG_STATUSES)}}, {"_id": 0, "id": 1, "roll_id": 1}):
        if t.get("roll_id") and not await db.inventory_rolls.find_one({"id": t["roll_id"]}, {"_id": 0, "id": 1}):
            res = await db.rfid_tags.update_one({"id": t["id"], "status": {"$in": list(LIVE_TAG_STATUSES)}}, {"$set": {
                "status": "retired", "retired_at": now_iso(), "retire_reason": "roll_tidak_ada"}})
            n += res.modified_count
    return n
