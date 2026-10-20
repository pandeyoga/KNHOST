"""L03 LN-033 — migrasi relasi lama `linked_po_id` → `special_orders.fulfillment.<key>`.

Default dry-run: hanya melaporkan matched/ambiguous/unresolved. `--apply` menulis relasi untuk yang
matched (dokumen PO/PR TIDAK dibuat ulang, tidak ada posting). `--rollback` membatalkan HANYA state migrasi yang
belum berubah. Ambiguous masuk `special_order_reconciliation`. `--only=<id,id>` membatasi ke OD tertentu.

AUD-MIG-01 — kandidat = fulfillment tidak ada / null / `{}`; penulisan dijaga syarat "masih kosong" dan hasilnya
diperiksa: laporan membedakan `matched` (klasifikasi) dari `applied` (benar-benar tertulis) dan `conflicts`
(diisi proses lain di antara baca & tulis — tidak ditimpa). Tautan PO hanya ditulis bila OD tertulis.
AUD-MIG-02 — apply menyimpan salinan persis hasil migrasi (`fulfillment_migration.<key>`); rollback menghapus state
hanya bila MASIH identik (update bersyarat atomik). State yang sudah dipakai operasional (versi/route/dokumen/riwayat
berubah) tidak dihapus: dicatat konflik di `special_order_reconciliation` untuk direkonsiliasi. Rollback ulang aman.

    cd /app/backend && python ../scripts/migrate_l03_ln033_fulfillment.py [--apply|--rollback] [--only=sord_1,sord_2]
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / "backend" / ".env")

from db import db  # noqa: E402
from core_utils import now_iso  # noqa: E402

TAG = "l03_ln033_fulfillment"
EMPTY = [{"fulfillment": {"$exists": False}}, {"fulfillment": None}, {"fulfillment": {}}]
PRISTINE_KEYS = {"route", "default_route", "source_mode", "reason", "deviation", "version", "status", "migrated",
                 "migrated_at", "pr_id", "pr_number", "docs"}


async def classify(od):
    items = od.get("items") or []
    po = await db.purchase_orders.find_one({"id": od["linked_po_id"]}, {"_id": 0, "id": 1, "po_number": 1, "items": 1, "status": 1})
    if not po:
        return "unresolved", None, "PO tertaut tidak ditemukan"
    if len(items) > 1:
        return "ambiguous", None, f"OD multi-item ({len(items)}) — PO tidak membawa item id"
    key = items[0]["id"] if items else "main"
    pid = (od.get("pricing") or {}).get("product_id") or od.get("linked_product_id") or ""
    lines = [i for i in po.get("items") or [] if i.get("product_id") == pid] if pid else []
    if len(lines) != 1:
        return "ambiguous", None, f"baris PO dengan produk {pid or '-'}: {len(lines)}"
    ln = lines[0]
    return "matched", {"key": key, "state": {
        "route": "purchase", "default_route": "", "source_mode": "legacy", "reason": "migrasi linked_po_id",
        "deviation": False, "version": 1, "status": "realized", "migrated": True, "migrated_at": now_iso(),
        "pr_id": od.get("linked_pr_id", ""), "pr_number": od.get("linked_pr_number", ""),
        "docs": [{"type": "po", "id": po["id"], "number": po.get("po_number", ""), "pr_id": od.get("linked_pr_id", ""),
                  "product_id": pid, "quantity": float(ln.get("quantity") or 0), "unit": ln.get("unit", ""),
                  "created_at": od.get("updated_at", "")}]}}, ""


def _empty(f: Any) -> bool:
    return not f   # tidak ada / None / {} → belum punya relasi fulfillment


async def _apply_one(od: Dict[str, Any], data: Dict[str, Any], rep: Dict[str, Any]) -> None:
    key, state = data["key"], data["state"]
    po_id = od["linked_po_id"]
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0, "special_order_item_key": 1}) or {}
    prev_key = po.get("special_order_item_key")
    row = {"id": od["id"], "number": od.get("number"), "po": od.get("linked_po_number")}
    if prev_key not in (None, "", key):
        rep["conflicts"].append({**row, "why": f"PO sudah tertaut ke item lain ({prev_key}) — tidak ditimpa"})
        return
    res = await db.special_orders.update_one(
        {"id": od["id"], "linked_po_id": po_id, "$or": EMPTY},
        {"$set": {"fulfillment": {key: state},
                  f"fulfillment_migration.{key}": {"source": TAG, "state": state, "po_id": po_id,
                                                   "po_prev_key": prev_key, "applied_at": now_iso()}}})
    if res.matched_count != 1:
        rep["conflicts"].append({**row, "why": "fulfillment sudah diisi proses lain di antara baca & tulis — tidak ditimpa"})
        return
    await db.purchase_orders.update_one({"id": po_id, "special_order_item_key": {"$in": [None, "", key]}},
                                        {"$set": {"special_order_item_key": key}})
    rep["applied"].append(row)


async def _rollback_one(od: Dict[str, Any], rep: Dict[str, Any]) -> None:
    logs = od.get("fulfillment_migration") or {}
    for key, cur in (od.get("fulfillment") or {}).items():
        if not (cur or {}).get("migrated"):
            continue
        log = logs.get(key) or {}
        row = {"id": od["id"], "number": od.get("number"), "key": key}
        if log.get("rolled_back_at"):
            continue
        if log.get("state") is not None:
            same = {f"fulfillment.{key}": log["state"]}   # kesamaan persis subdokumen = belum berubah sejak migrasi
        else:   # migrasi versi lama (tanpa salinan): hanya bentuk murni hasil migrasi yang boleh dibatalkan
            if set(cur) - PRISTINE_KEYS or cur.get("version") != 1 or cur.get("route") != "purchase" \
                    or len(cur.get("docs") or []) != 1:
                same = None
            else:
                same = {f"fulfillment.{key}": cur}
        res = await db.special_orders.update_one(
            {"id": od["id"], **same}, {"$unset": {f"fulfillment.{key}": ""},
                                       "$set": {f"fulfillment_migration.{key}.rolled_back_at": now_iso()}}) \
            if same else None
        if not res or res.matched_count != 1:
            why = (f"state fulfillment.{key} sudah berubah sesudah migrasi (versi {cur.get('version')}, route "
                   f"{cur.get('route')}, {len(cur.get('docs') or [])} dokumen) — tidak dihapus; rekonsiliasi manual")
            rep["rollback_conflicts"].append({**row, "why": why})
            await db.special_order_reconciliation.update_one(
                {"special_order_id": od["id"], "source": TAG, "reason": "rollback_conflict", "item_key": key},
                {"$set": {"detail": why, "updated_at": now_iso()},
                 "$setOnInsert": {"special_order_id": od["id"], "source": TAG, "reason": "rollback_conflict",
                                  "item_key": key, "created_at": now_iso()}}, upsert=True)
            continue
        po_id = log.get("po_id") or ((cur.get("docs") or [{}])[0]).get("id")
        if po_id:   # tautan PO dipulihkan hanya bila masih tautan milik migrasi ini
            prev = log.get("po_prev_key")
            upd = {"$set": {"special_order_item_key": prev}} if prev else {"$unset": {"special_order_item_key": ""}}
            await db.purchase_orders.update_one({"id": po_id, "special_order_item_key": key}, upd)
        rep["rolled_back"].append(row)


async def main(mode: str, only: Optional[List[str]] = None) -> Dict[str, Any]:
    rep: Dict[str, Any] = {"mode": mode, "matched": [], "ambiguous": [], "unresolved": [], "applied": [],
                           "conflicts": [], "skipped_has_fulfillment": 0, "rolled_back": [], "rollback_conflicts": []}
    scope: Dict[str, Any] = {"id": {"$in": only}} if only else {}
    if mode == "rollback":
        async for od in db.special_orders.find({**scope, "fulfillment": {"$exists": True}},
                                               {"_id": 0, "id": 1, "number": 1, "fulfillment": 1, "fulfillment_migration": 1}):
            await _rollback_one(od, rep)
        rec = {"source": TAG, "reason": {"$in": ["ambiguous", "unresolved"]}}
        if only:
            rec["special_order_id"] = {"$in": only}
        await db.special_order_reconciliation.delete_many(rec)
        rep["counts"] = {k: len(rep[k]) for k in ("rolled_back", "rollback_conflicts")}
        print(json.dumps(rep, indent=1, ensure_ascii=False))
        return rep
    async for od in db.special_orders.find({**scope, "linked_po_id": {"$nin": [None, ""]}}, {"_id": 0}):
        if not _empty(od.get("fulfillment")):
            rep["skipped_has_fulfillment"] += 1
            continue
        kind, data, why = await classify(od)
        rep[kind].append({"id": od["id"], "number": od.get("number"), "po": od.get("linked_po_number"), "why": why})
        if mode != "apply":
            continue
        if kind == "matched":
            await _apply_one(od, data, rep)
        else:
            await db.special_order_reconciliation.update_one(
                {"special_order_id": od["id"], "source": TAG, "reason": kind},
                {"$setOnInsert": {"special_order_id": od["id"], "source": TAG, "reason": kind, "detail": why,
                                  "linked_po_id": od["linked_po_id"], "created_at": now_iso()}}, upsert=True)
    rep["counts"] = {k: len(rep[k]) for k in ("matched", "ambiguous", "unresolved", "applied", "conflicts")}
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    return rep


def _only(argv: List[str]) -> Optional[List[str]]:
    for a in argv:
        if a.startswith("--only="):
            return [x for x in a.split("=", 1)[1].split(",") if x]
    return None


if __name__ == "__main__":
    asyncio.run(main("apply" if "--apply" in sys.argv else "rollback" if "--rollback" in sys.argv else "dry_run",
                     _only(sys.argv)))
