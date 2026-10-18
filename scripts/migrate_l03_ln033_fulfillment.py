"""L03 LN-033 — migrasi relasi lama `linked_po_id` → `special_orders.fulfillment.<key>`.

Default dry-run: hanya melaporkan matched/ambiguous/unresolved. `--apply` menulis relasi untuk yang
matched (dokumen PO/PR TIDAK dibuat ulang, tidak ada posting). `--rollback` menghapus hanya field
yang ditulis migrasi ini (`fulfillment.<key>.migrated=true`). Ambiguous masuk `special_order_reconciliation`.

    cd /app/backend && python ../scripts/migrate_l03_ln033_fulfillment.py [--apply|--rollback]
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / "backend" / ".env")

from db import db  # noqa: E402
from core_utils import now_iso  # noqa: E402

TAG = "l03_ln033_fulfillment"


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


async def main(mode: str) -> None:
    rep = {"mode": mode, "matched": [], "ambiguous": [], "unresolved": [], "skipped_has_fulfillment": 0, "rolled_back": 0}
    if mode == "rollback":
        async for od in db.special_orders.find({"fulfillment": {"$exists": True}}, {"_id": 0, "id": 1, "fulfillment": 1}):
            unset = {f"fulfillment.{k}": "" for k, v in (od.get("fulfillment") or {}).items() if (v or {}).get("migrated")}
            if unset:
                await db.special_orders.update_one({"id": od["id"]}, {"$unset": unset})
                rep["rolled_back"] += 1
        await db.special_order_reconciliation.delete_many({"source": TAG})
        print(json.dumps(rep, indent=1))
        return
    async for od in db.special_orders.find({"linked_po_id": {"$nin": [None, ""]}}, {"_id": 0}):
        if od.get("fulfillment"):
            rep["skipped_has_fulfillment"] += 1
            continue
        kind, data, why = await classify(od)
        rep[kind].append({"id": od["id"], "number": od.get("number"), "po": od.get("linked_po_number"), "why": why})
        if mode != "apply":
            continue
        if kind == "matched":
            await db.special_orders.update_one({"id": od["id"], "fulfillment": {"$exists": False}},
                                               {"$set": {f"fulfillment.{data['key']}": data["state"]}})
            await db.purchase_orders.update_one({"id": od["linked_po_id"]}, {"$set": {"special_order_item_key": data["key"]}})
        else:
            await db.special_order_reconciliation.update_one(
                {"special_order_id": od["id"], "source": TAG},
                {"$setOnInsert": {"special_order_id": od["id"], "source": TAG, "reason": kind, "detail": why,
                                  "linked_po_id": od["linked_po_id"], "created_at": now_iso()}}, upsert=True)
    rep["counts"] = {k: len(rep[k]) for k in ("matched", "ambiguous", "unresolved")}
    print(json.dumps(rep, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main("apply" if "--apply" in sys.argv else "rollback" if "--rollback" in sys.argv else "dry_run"))
