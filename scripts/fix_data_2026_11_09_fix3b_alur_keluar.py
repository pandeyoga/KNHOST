#!/usr/bin/env python3
"""FIX-3b — rapikan data alur BARANG KELUAR, potong & RFID yang lahir dari celah yang sudah ditutup kode. HANYA DB uji
`kn_test_trial`.

Langkah (semua idempoten; tanpa `--apply` = dry-run: hanya menghitung & menampilkan contoh):
  1. `rfid_simulation_off` — Mode simulasi RFID (`wms.rfid_simulation`) yang MENYALA untuk PT nyata (ent_ksc, ent_kanda,
                             ent_82b52ed6ee8b) → dimatikan (catatan pra-pilot B2b RFID-9, keputusan K-B2b-09). Nilai
                             lama disimpan di jejak `migrations`.
  2. `shipped_roll_released` — roll yang tercantum di Surat Jalan aktif tetapi berstatus `available` (jejak STM-OUT-1:
                             resolve eskalasi melepas roll yang sudah dikirim) → kembali `in_transit_sales` milik SO-nya
                             (atau `delivered` bila SJ-nya sudah ber-POD).
  3. `dead_so_reservations` — roll `reserved/committed` yang `reserved_ref`-nya SO terminal (batal/kedaluwarsa/selesai)
                             atau SO `draft` (jejak STM-OUT-4) → `available` + mutasi `release_reservation`.
  4. `pod_rolls_in_transit` — roll `in_transit_sales` yang SJ-nya sudah ber-POD (jejak FLW-OUT-2) → `delivered`.
  5. `escalation_on_terminal` — tugas ambil `cancelled/dispatched` yang eskalasinya masih `pending_review` (STM-OUT-2)
                             → eskalasi `cancelled` (tanpa mengubah status tugas).
  6. `stale_transfer_marker` — `transfer_prior_status` basi pada roll yang tidak lagi dalam transfer (FLW-OUT-11) → hapus.
  7. `consumed_revived`     — roll `available` panjang 0 yang ber-`consumed_ref` (jejak MKO-03) → `consumed`.
  8. `sample_paid_cancelled` — SO sampel berbayar `cancelled` dengan `sample_payment_status = approved` (CUT-6) →
                             `refund_pending`.
  9. `epc_reuse_report`     — LAPORAN: EPC yang muncul di >1 tag (B2b RFID-2) — tidak diubah otomatis (perlu cek fisik).
Tidak menyentuh: saldo/jurnal (rebuild saldo segmen yang rolnya berubah saja), data UAT "test" (SORD-261023-0003).
Jejak: satu dokumen `migrations` (`id = fix_data_2026_11_09_fix3b_alur_keluar`).

Pakai (di dalam kontainer backend, repo = /app):
    python /app/scripts/fix_data_2026_11_09_fix3b_alur_keluar.py --db kn_test_trial            # dry-run (bawaan)
    python /app/scripts/fix_data_2026_11_09_fix3b_alur_keluar.py --db kn_test_trial --apply
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

ALLOWED_DB = "kn_test_trial"


def _args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True, help=f"nama DB — HANYA {ALLOWED_DB} yang diizinkan")
    ap.add_argument("--apply", action="store_true", help="terapkan (tanpa ini = dry-run)")
    return ap.parse_args()


ARGS = _args()
if ARGS.db != ALLOWED_DB:
    print(f"DITOLAK: skrip ini hanya untuk DB uji {ALLOWED_DB}; --db {ARGS.db} tidak diproses.")
    sys.exit(2)
os.environ["DB_NAME"] = ARGS.db          # db.py membaca DB_NAME saat di-import
BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from core_utils import new_id, now_iso  # noqa: E402
from db import db  # noqa: E402

FLAG = "fix_data_2026_11_09_fix3b_alur_keluar"
ACTOR = "Sistem (FIX-3b rapikan data alur keluar)"
PROTECTED_ORDERS = {"SORD-261023-0003"}   # data UAT "test" — jangan disentuh
REAL_PT = ("ent_ksc", "ent_kanda", "ent_82b52ed6ee8b")
SO_DEAD = ("cancelled", "expired", "done", "rejected", "draft")
SEGMENTS: set = set()


async def _protected_so_ids() -> set:
    return {o["id"] async for o in db.sales_orders.find(
        {"$or": [{"number": {"$in": list(PROTECTED_ORDERS)}}, {"order_number": {"$in": list(PROTECTED_ORDERS)}}]},
        {"_id": 0, "id": 1})}


async def step_rfid_simulation_off(apply: bool) -> dict:
    rows = []
    async for c in db.config_values.find({"key": "wms.rfid_simulation", "value": True,
                                          "$or": [{"scope_type": "entity", "scope_id": {"$in": list(REAL_PT)}},
                                                  {"scope_type": "global"}]}, {"_id": 0}):
        rows.append({"id": c.get("id"), "scope_type": c.get("scope_type"), "scope_id": c.get("scope_id")})
        if apply:
            await db.config_values.update_one({"id": c.get("id"), "key": "wms.rfid_simulation"}, {"$set": {
                "value": False, "updated_at": now_iso(), "updated_by": ACTOR,
                "note": "FIX-3b (B2b RFID-9): mode simulasi dimatikan sebelum reader nyata dipasang"}})
    return {"count": len(rows), "rows": rows}


async def step_shipped_roll_released(apply: bool, protected: set) -> dict:
    ids = []
    async for s in db.shipments.find({"status": {"$nin": ["cancelled", "void", "voided"]}},
                                     {"_id": 0, "id": 1, "order_id": 1, "rolls.roll_id": 1, "logistics_status": 1}):
        if s.get("order_id") in protected:
            continue
        rids = [r.get("roll_id") for r in s.get("rolls") or [] if r.get("roll_id")]
        if not rids:
            continue
        async for r in db.inventory_rolls.find({"id": {"$in": rids}, "status": "available"},
                                               {"_id": 0, "id": 1, "product_id": 1, "warehouse_id": 1,
                                                "owner_entity_id": 1}):
            ids.append(r["id"])
            if apply:
                to = "delivered" if s.get("logistics_status") in ("delivered", "completed") else "in_transit_sales"
                await db.inventory_rolls.update_one({"id": r["id"], "status": "available"}, {"$set": {
                    "status": to, "reserved_ref": {"type": "sales_order", "id": s["order_id"]}, "updated_at": now_iso(),
                    "fix3b_note": f"dipulihkan dari SJ {s['id']} (STM-OUT-1)"}})
                SEGMENTS.add((r["product_id"], r["warehouse_id"], r.get("owner_entity_id")))
    return {"count": len(ids), "ids": ids[:50]}


async def step_dead_so_reservations(apply: bool, protected: set) -> dict:
    dead = {o["id"] async for o in db.sales_orders.find({"status": {"$in": list(SO_DEAD)}}, {"_id": 0, "id": 1})} - protected
    ids = []
    async for r in db.inventory_rolls.find({"reserved_ref.type": "sales_order", "reserved_ref.id": {"$in": list(dead)},
                                            "status": {"$in": ["reserved", "committed", "picked", "packed"]}},
                                           {"_id": 0}):
        ids.append(r["id"])
        if apply:
            res = await db.inventory_rolls.update_one({"id": r["id"], "status": r["status"]}, {"$set": {
                "status": "available", "reserved_ref": None, "updated_at": now_iso()}})
            if res.modified_count:
                await db.inventory_movements.insert_one({
                    "id": new_id("mov"), "product_id": r["product_id"], "warehouse_id": r["warehouse_id"],
                    "owner_entity_id": r.get("owner_entity_id"), "movement_type": "release_reservation",
                    "quantity": round(float(r.get("length_remaining") or 0), 2), "unit": r.get("unit", "meter"),
                    "lot": r.get("lot", ""), "roll_id": r["id"], "qty_rolls": 1,
                    "source_document": r["reserved_ref"]["id"], "timestamp": now_iso(),
                    "note": "FIX-3b: reservasi milik SO terminal/draf dilepas (STM-OUT-4)"})
                SEGMENTS.add((r["product_id"], r["warehouse_id"], r.get("owner_entity_id")))
    return {"count": len(ids), "ids": ids[:50]}


async def step_pod_rolls(apply: bool, protected: set) -> dict:
    ids = []
    async for s in db.shipments.find({"status": {"$nin": ["cancelled", "void", "voided"]},
                                      "logistics_status": {"$in": ["delivered", "completed"]}},
                                     {"_id": 0, "id": 1, "order_id": 1, "rolls.roll_id": 1}):
        if s.get("order_id") in protected:
            continue
        rids = [r.get("roll_id") for r in s.get("rolls") or [] if r.get("roll_id")]
        async for r in db.inventory_rolls.find({"id": {"$in": rids}, "status": "in_transit_sales"},
                                               {"_id": 0, "id": 1, "product_id": 1, "warehouse_id": 1,
                                                "owner_entity_id": 1}):
            ids.append(r["id"])
            if apply:
                await db.inventory_rolls.update_one({"id": r["id"], "status": "in_transit_sales"}, {"$set": {
                    "status": "delivered", "delivered_at": now_iso(), "delivered_via": "fix3b_pod_per_sj",
                    "updated_at": now_iso()}})
                SEGMENTS.add((r["product_id"], r["warehouse_id"], r.get("owner_entity_id")))
    return {"count": len(ids), "ids": ids[:50]}


async def step_escalation_on_terminal(apply: bool) -> dict:
    ids = []
    async for t in db.wms_tasks.find({"flow_type": "outbound", "status": {"$in": ["cancelled", "dispatched"]},
                                      "escalation.status": {"$in": ["pending_review", "resolving"]}},
                                     {"_id": 0, "id": 1}):
        ids.append(t["id"])
        if apply:
            await db.wms_tasks.update_one({"id": t["id"]}, {"$set": {
                "escalation.status": "cancelled", "escalation.cancelled_at": now_iso(),
                "escalation.resolution_notes": "FIX-3b: eskalasi atas tugas terminal ditutup (STM-OUT-2)"}})
    return {"count": len(ids), "ids": ids[:50]}


async def step_stale_transfer_marker(apply: bool) -> dict:
    ids = []
    async for r in db.inventory_rolls.find({"transfer_prior_status": {"$nin": [None, ""]},
                                            "status": {"$nin": ["in_transit_transfer"]},
                                            "reserved_ref.type": {"$ne": "wh_transfer"},
                                            "transfer_ref": {"$in": [None, {}]}}, {"_id": 0, "id": 1}):
        ids.append(r["id"])
        if apply:
            await db.inventory_rolls.update_one({"id": r["id"]}, {"$set": {"transfer_prior_status": None}})
    return {"count": len(ids), "ids": ids[:50]}


async def step_consumed_revived(apply: bool) -> dict:
    ids = []
    async for r in db.inventory_rolls.find({"status": "available", "consumed_ref": {"$nin": [None, ""]},
                                            "length_remaining": {"$lte": 0}},
                                           {"_id": 0, "id": 1, "product_id": 1, "warehouse_id": 1, "owner_entity_id": 1}):
        ids.append(r["id"])
        if apply:
            await db.inventory_rolls.update_one({"id": r["id"], "status": "available"}, {"$set": {
                "status": "consumed", "updated_at": now_iso(), "fix3b_note": "MKO-03: roll habis dihidupkan retur bahan"}})
            SEGMENTS.add((r["product_id"], r["warehouse_id"], r.get("owner_entity_id")))
    return {"count": len(ids), "ids": ids[:50]}


async def step_sample_paid_cancelled(apply: bool, protected: set) -> dict:
    ids = []
    async for o in db.sales_orders.find({"status": "cancelled", "sample_billing": "paid",
                                         "sample_payment_status": "approved"}, {"_id": 0, "id": 1}):
        if o["id"] in protected:
            continue
        ids.append(o["id"])
        if apply:
            await db.sales_orders.update_one({"id": o["id"], "sample_payment_status": "approved"}, {"$set": {
                "sample_payment_status": "refund_pending", "sample_payment_cancel_reason": "FIX-3b: SO sampel batal (CUT-6)"}})
    return {"count": len(ids), "ids": ids[:50]}


async def report_epc_reuse() -> dict:
    rows = []
    async for g in db.rfid_tags.aggregate([{"$group": {"_id": "$epc", "n": {"$sum": 1}, "rolls": {"$addToSet": "$roll_id"},
                                                       "statuses": {"$push": "$status"}}},
                                           {"$match": {"n": {"$gt": 1}}}]):
        if len(g.get("rolls") or []) > 1:
            rows.append({"epc": g["_id"], "rolls": g["rolls"][:5], "statuses": g["statuses"][:5]})
    return {"count": len(rows), "rows": rows[:50]}


async def main() -> None:
    apply = ARGS.apply
    if apply and await db.migrations.find_one({"id": FLAG, "applied": True}):
        print(f"{FLAG} sudah pernah diterapkan — langkah idempoten tetap dijalankan ulang (hanya sisa yang dirapikan).")
    protected = await _protected_so_ids()
    out = {
        "rfid_simulation_off": await step_rfid_simulation_off(apply),
        "shipped_roll_released": await step_shipped_roll_released(apply, protected),
        "dead_so_reservations": await step_dead_so_reservations(apply, protected),
        "pod_rolls_in_transit": await step_pod_rolls(apply, protected),
        "escalation_on_terminal": await step_escalation_on_terminal(apply),
        "stale_transfer_marker": await step_stale_transfer_marker(apply),
        "consumed_revived": await step_consumed_revived(apply),
        "sample_paid_cancelled": await step_sample_paid_cancelled(apply, protected),
        "epc_reuse_report": await report_epc_reuse(),
    }
    if apply and SEGMENTS:
        from services.roll_service import rebuild_balance
        for p, w, o in SEGMENTS:
            await rebuild_balance(p, w, o)
    print(("DITERAPKAN" if apply else "DRY-RUN (tidak ada yang diubah)") + f" — DB {ARGS.db}")
    for k, v in out.items():
        print(f"  {k:24s} {v['count']:>5}  contoh: {(v.get('ids') or v.get('rows') or [])[:4]}")
    if apply:
        await db.migrations.update_one({"id": FLAG}, {"$set": {"id": FLAG, "applied": True, "at": now_iso(), "by": ACTOR,
                                                               "result": out}}, upsert=True)


if __name__ == "__main__":
    asyncio.run(main())
