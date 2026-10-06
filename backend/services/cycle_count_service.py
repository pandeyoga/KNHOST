"""CYCLE COUNT RFID — stock opname kilat via sweep handheld.

Expected = seluruh tag aktif roll fisik di gudang → scan handheld → rekonsiliasi:
found / missing (ada di sistem, tak terbaca) / extra (terbaca tapi milik gudang
lain atau EPC asing). LAPORAN SAJA — RFID tidak mengubah kuantitas (Roll-as-SSOT);
selisih ditindaklanjuti manual/insiden.
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso, next_doc_number, safe_doc
from services.roll_service import PHYSICAL_ROLL_STATUSES  # RF-17 — SATU definisi stok fisik di lokasi


async def start(warehouse_id: str, scope_ids: List[str], actor_name: str) -> Dict[str, Any]:
    wh = await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0, "name": 1})
    if not wh:
        raise HTTPException(status_code=404, detail="Gudang tidak ditemukan")
    scope_key = sorted(set(scope_ids))  # RF-08/RF-09 — sesi & hasil diikat ke daftar entitas pembuat
    existing = await db.rfid_verify_sessions.find_one(
        {"kind": "cycle_count", "warehouse_id": warehouse_id, "status": "open",
         "scope_entity_ids": scope_key}, {"_id": 0})
    if existing:
        return safe_doc(existing)
    eligible = await db.inventory_rolls.find({
        "warehouse_id": warehouse_id, "owner_entity_id": {"$in": scope_ids},
        "status": {"$in": PHYSICAL_ROLL_STATUSES}, "length_remaining": {"$gt": 0},
    }, {"_id": 0, "id": 1, "roll_no": 1, "rfid_tag_id": 1, "status": 1}).to_list(20000)
    rolls = [r for r in eligible if r.get("rfid_tag_id")]
    if not rolls:
        raise HTTPException(status_code=400, detail="Tidak ada roll ber-tag di gudang ini.")
    tags = {t["id"]: t for t in await db.rfid_tags.find(
        {"id": {"$in": [r["rfid_tag_id"] for r in rolls]}, "status": "active"},
        {"_id": 0, "id": 1, "epc": 1, "sku": 1, "product_name": 1}).to_list(20000)}
    expected = []
    for r in rolls:
        t = tags.get(r["rfid_tag_id"])
        if t:
            expected.append({"epc": t["epc"], "roll_id": r["id"], "roll_no": r.get("roll_no", ""),
                             "sku": t.get("sku", ""), "product_name": t.get("product_name", "")})
    tagged_ids = {e["roll_id"] for e in expected}
    untagged = [{"roll_id": r["id"], "roll_no": r.get("roll_no", ""), "status": r.get("status")}
                for r in eligible if r["id"] not in tagged_ids]
    sess = {
        "id": new_id("rvs"), "kind": "cycle_count", "print_job_id": None,
        "warehouse_id": warehouse_id, "warehouse_name": wh.get("name", ""),
        "owner_entity_id": scope_ids[0] if len(scope_ids) == 1 else None,
        "scope_entity_ids": scope_key,
        "expected": expected, "scanned_epcs": [], "missing": [], "extra": [], "scan_sources": [],
        "eligible_count": len(eligible), "untagged_count": len(untagged), "untagged": untagged[:500],
        "status": "open", "created_at": now_iso(), "created_by": actor_name,
        "completed_at": None,
    }
    await db.rfid_verify_sessions.insert_one(dict(sess))
    return safe_doc(sess)


def session_scope(doc: Dict[str, Any]) -> List[str]:
    """Entitas pemilik sesi/hasil count (record lama: owner_entity_id tunggal)."""
    return list(doc.get("scope_entity_ids") or ([doc["owner_entity_id"]] if doc.get("owner_entity_id") else []))


def _in_scope(doc: Optional[Dict[str, Any]], scope_ids: List[str]) -> bool:
    owners = session_scope(doc or {})
    return bool(owners) and set(owners) <= set(scope_ids)


async def complete(session_id: str, actor_name: str, scope_ids: List[str]) -> Dict[str, Any]:
    sess = await db.rfid_verify_sessions.find_one({"id": session_id}, {"_id": 0})
    if not sess or sess.get("kind") != "cycle_count" or not _in_scope(sess, scope_ids):
        raise HTTPException(status_code=404, detail="Sesi cycle count tidak ditemukan")
    if sess["status"] != "open":
        raise HTTPException(status_code=400, detail="Sesi sudah selesai")
    # Sesi 14 — klaim saga sesi (status open) sesudah validasi; klik ganda/balapan → 409, satu CC saja.
    from services import atomic_claim as _saga
    await _saga.claim("rfid_verify_sessions", session_id, "cycle_count_complete", actor=actor_name,
                      precondition={"status": "open"})
    sess = await db.rfid_verify_sessions.find_one({"id": session_id}, {"_id": 0})  # RF-10 — snapshot sesudah klaim
    simulated = "simulated" in (sess.get("scan_sources") or [])  # RF-07 — laporan ditandai simulasi
    expected = {e["epc"]: e for e in sess.get("expected", [])}
    scanned = set(sess.get("scanned_epcs") or [])
    missing = [expected[e] for e in expected if e not in scanned]
    extra_epcs = sorted(scanned - set(expected))
    extra_items = []
    for epc in extra_epcs:
        tag = await db.rfid_tags.find_one({"epc": epc, "status": "active"}, {"_id": 0})
        if not tag:
            extra_items.append({"epc": epc, "kind": "unknown", "note": "EPC asing (tak terdaftar)"})
            continue
        roll = await db.inventory_rolls.find_one({"id": tag["roll_id"]},
                                                 {"_id": 0, "roll_no": 1, "warehouse_id": 1})
        wh = await db.warehouses.find_one({"id": (roll or {}).get("warehouse_id")},
                                          {"_id": 0, "name": 1}) or {}
        extra_items.append({"epc": epc, "kind": "misplaced", "roll_no": (roll or {}).get("roll_no"),
                            "sku": tag.get("sku"), "note": f"Terdaftar di {wh.get('name', 'gudang lain')} — salah lokasi"})
    found = len(expected) - len(missing)
    # RF-17 — metrik terpisah; akurasi count = ditemukan / (eligible + extra): 100% hanya bila SEMUA roll fisik
    # ber-tag, terbaca, dan tidak ada EPC asing/salah lokasi.
    eligible_n = int(sess.get("eligible_count") or len(expected))
    untagged_n = int(sess.get("untagged_count") or 0)
    pct = lambda a, b: round(a / b * 100, 1) if b else 0.0  # noqa: E731
    accuracy = pct(found, eligible_n + len(extra_items)) if (eligible_n + len(extra_items)) else 100.0
    metrics = {"eligible_count": eligible_n, "tagged_count": len(expected), "untagged_count": untagged_n,
               "tag_coverage_pct": pct(len(expected), eligible_n), "read_recall_pct": pct(found, len(expected)),
               "extra_rate_pct": pct(len(extra_items), found + len(extra_items)),
               "unresolved_count": len(missing) + len(extra_items) + untagged_n}
    now = now_iso()
    # G3 D4-CC-01 — satu sesi = satu hasil: retry (ack hilang / update sesi gagal) MENGADOPSI hasil lama.
    prior = await db.rfid_cycle_counts.find_one({"session_id": session_id}, {"_id": 0})
    if prior:
        await db.rfid_verify_sessions.update_one({"id": session_id}, _saga.finish_set({
            "status": "completed", "completed_at": prior.get("created_at", now), "cycle_count_id": prior["id"]}))
        return safe_doc(prior)
    cc = {
        "id": f"rcc_{session_id}",
        "cc_number": await next_doc_number("rfid_cycle_counts", "cc_number", "CC"),
        "session_id": session_id, "warehouse_id": sess["warehouse_id"],
        "scope_entity_ids": session_scope(sess),
        "warehouse_name": sess.get("warehouse_name", ""),
        "expected_count": len(expected), "found_count": found,
        "missing_count": len(missing), "extra_count": len(extra_items),
        "accuracy_pct": accuracy, "simulated": simulated, **metrics,
        "untagged_items": (sess.get("untagged") or [])[:500],
        "missing_items": [safe_doc(m) for m in missing][:500],
        "extra_items": extra_items[:500],
        "created_at": now, "created_by": actor_name,
    }
    try:
        await db.rfid_cycle_counts.insert_one(dict(cc))
    except Exception:  # noqa: BLE001 — id deterministik: pemenang balapan sudah menulis hasilnya
        won = await db.rfid_cycle_counts.find_one({"id": cc["id"]}, {"_id": 0})
        if not won:
            raise
        cc = won
    await db.rfid_verify_sessions.update_one({"id": session_id}, _saga.finish_set({
        "status": "completed",
        "result": "simulated" if simulated else ("clean" if not missing and not extra_items and not untagged_n else "with_issues"),
        "missing": [m["epc"] for m in missing], "extra": extra_epcs,
        "completed_at": now, "cycle_count_id": cc["id"]}))
    return safe_doc(cc)


async def list_counts(warehouse_id: Optional[str], scope_ids: List[str], limit: int = 30) -> List[Dict[str, Any]]:
    # RF-08 — hanya hasil yang seluruh entitasnya dalam scope pemanggil
    q: Dict[str, Any] = {"scope_entity_ids": {"$exists": True, "$ne": [],
                                              "$not": {"$elemMatch": {"$nin": list(scope_ids)}}}}
    if warehouse_id:
        q["warehouse_id"] = warehouse_id
    rows = await db.rfid_cycle_counts.find(q, {"_id": 0, "missing_items": 0, "extra_items": 0}) \
        .sort("created_at", -1).to_list(limit)
    return [safe_doc(r) for r in rows]


async def get_count(cc_id: str, scope_ids: List[str]) -> Dict[str, Any]:
    cc = await db.rfid_cycle_counts.find_one({"id": cc_id}, {"_id": 0})
    if not cc or not _in_scope(cc, scope_ids):
        raise HTTPException(status_code=404, detail="Cycle count tidak ditemukan")
    return safe_doc(cc)


async def backfill_scope() -> int:
    """RF-08 — sesi/hasil lama tanpa scope: turunkan dari owner roll yang diharapkan (idempotent)."""
    n = 0
    async for sess in db.rfid_verify_sessions.find(
            {"kind": "cycle_count", "scope_entity_ids": {"$exists": False}}, {"_id": 0}):
        owners = session_scope(sess)
        if not owners:
            ids = [e.get("roll_id") for e in sess.get("expected") or [] if e.get("roll_id")]
            owners = sorted(set(await db.inventory_rolls.distinct("owner_entity_id", {"id": {"$in": ids}})) - {None, ""})
        await db.rfid_verify_sessions.update_one({"id": sess["id"]}, {"$set": {"scope_entity_ids": owners}})
        await db.rfid_cycle_counts.update_many({"session_id": sess["id"], "scope_entity_ids": {"$exists": False}},
                                               {"$set": {"scope_entity_ids": owners}})
        n += 1
    return n
