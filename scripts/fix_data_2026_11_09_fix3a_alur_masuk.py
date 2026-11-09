#!/usr/bin/env python3
"""FIX-3a — rapikan data alur BARANG MASUK yang lahir dari celah yang sudah ditutup kode. HANYA DB uji `kn_test_trial`.

Langkah (semua idempoten; tanpa `--apply` = dry-run: hanya menghitung & menampilkan contoh):
  1. `transfer_returned`  — transfer `completed` "actual_receipt" padahal 0 roll diterima & ≥1 roll kembali ke asal
                            → status `returned` (keputusan koordinator D10, B2a FLW-IN-10).
  2. `transfer_hold`      — roll berstatus `hold` hasil "diterima ditahan" transfer → `blocked` + `hold{held}` (satu
                            representasi tahan; dilepas lewat Lepas Tahanan) (B2a STM-IN-04).
  3. `fake_tag_ref`       — roll hasil terima PO jalur lama yang `rfid_tag_id`-nya teks bebas isian "Roll ID" (tidak ada di
                            `rfid_tags`) → nilai dipindah ke `supplier_roll_no` (bila kosong), `rfid_tag_id` dikosongkan
                            (B3b INP-01, B2a FLW-IN-08).
  4. `opname_dead_tags`   — tag RFID aktif/menunggu cetak yang menunjuk roll yang sudah habis/dihapus lewat opname
                            (`lost_in_count` / `consumed` & 0) → `retired` (B2a OPN-04).
  5. `escalation_posted`  — tugas masuk berstatus `escalated` yang dieskalasi SESUDAH barang diposting (`pre_status`
                            qc_pending/qc_rejected/completed) → dikembalikan ke status itu (eskalasi ditandai selesai
                            sistem) supaya tidak bisa diputus ke `qc_check` (FLW-IN-01).
  6. `over_received_report` — LAPORAN saja: baris PO dengan received_qty > qty × 1,5 (jejak FLW-IN-01) untuk ditinjau
                            pembelian/finance; tidak diubah otomatis.
Tidak menyentuh: saldo/jurnal (roll & GL tidak diubah nilainya), data UAT "test" (SORD-261023-0003).
Jejak: satu dokumen `migrations` (`id = fix_data_2026_11_09_fix3a_alur_masuk`) berisi hitungan & id yang diubah.

Pakai (di dalam kontainer backend, repo = /app):
    python /app/scripts/fix_data_2026_11_09_fix3a_alur_masuk.py --db kn_test_trial            # dry-run (bawaan)
    python /app/scripts/fix_data_2026_11_09_fix3a_alur_masuk.py --db kn_test_trial --apply
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

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402

FLAG = "fix_data_2026_11_09_fix3a_alur_masuk"
ACTOR = "Sistem (FIX-3a rapikan data alur masuk)"
PROTECTED_ORDERS = {"SORD-261023-0003"}   # data UAT "test" — jangan disentuh


async def step_transfer_returned(apply: bool) -> dict:
    ids = []
    async for t in db.warehouse_transfers.find({"status": "completed", "completion_basis": "actual_receipt"},
                                               {"_id": 0, "id": 1, "code": 1}):
        if await db.inventory_rolls.count_documents({"last_transfer.ref_id": t["id"]}):
            continue
        if not await db.inventory_rolls.count_documents({"returned_from_transfer.ref_id": t["id"]}):
            continue
        ids.append(t["id"])
        if apply:
            await db.warehouse_transfers.update_one(
                {"id": t["id"], "status": "completed"},
                {"$set": {"status": "returned", "completion_basis": "all_returned", "updated_at": now_iso(),
                          "fixed_by": FLAG},
                 "$push": {"status_history": {"status": "returned", "timestamp": now_iso(), "user": ACTOR,
                                              "note": "data lama: 0 roll diterima, semua kembali ke asal"}}})
    return {"count": len(ids), "ids": ids[:50]}


async def step_transfer_hold(apply: bool) -> dict:
    ids = []
    async for r in db.inventory_rolls.find({"status": "hold", "last_transfer.outcome": "hold"},
                                           {"_id": 0, "id": 1, "last_transfer": 1, "hold": 1}):
        ids.append(r["id"])
        if apply:
            lt = r.get("last_transfer") or {}
            await db.inventory_rolls.update_one({"id": r["id"], "status": "hold"}, {"$set": {
                "status": "blocked", "updated_at": now_iso(),
                "hold": {"held": True, "reason": f"Diterima dengan pengecualian aturan gudang (transfer {lt.get('code') or ''})",
                         "by": lt.get("received_by") or ACTOR, "at": lt.get("date") or now_iso(),
                         "prev_status": "available", "source": "transfer_rule"}},
                "$push": {"hold_history": {"action": "hold", "reason": "FIX-3a: status 'hold' transfer → tahan baku",
                                           "by": ACTOR, "at": now_iso(), "status_from": "hold", "status_to": "blocked"}}})
    if apply and ids:
        from services.roll_service import rebuild_balance
        seen = set()
        async for r in db.inventory_rolls.find({"id": {"$in": ids}}, {"_id": 0, "product_id": 1, "warehouse_id": 1,
                                                                      "owner_entity_id": 1}):
            k = (r["product_id"], r["warehouse_id"], r.get("owner_entity_id"))
            if k not in seen:
                seen.add(k)
                await rebuild_balance(*k)
    return {"count": len(ids), "ids": ids[:50]}


async def step_fake_tag_ref(apply: bool) -> dict:
    rows = []
    async for r in db.inventory_rolls.find({"acquired.via": "inbound", "rfid_tag_id": {"$nin": [None, ""]}},
                                           {"_id": 0, "id": 1, "rfid_tag_id": 1, "supplier_roll_no": 1}):
        if await db.rfid_tags.find_one({"id": r["rfid_tag_id"]}, {"_id": 1}):
            continue
        rows.append(r)
        if apply:
            upd = {"rfid_tag_id": None, "updated_at": now_iso(), "fixed_by": FLAG,
                   "legacy_roll_id_input": r["rfid_tag_id"]}
            if not r.get("supplier_roll_no"):
                upd["supplier_roll_no"] = str(r["rfid_tag_id"]).strip()
            await db.inventory_rolls.update_one({"id": r["id"], "rfid_tag_id": r["rfid_tag_id"]}, {"$set": upd})
    return {"count": len(rows), "ids": [r["id"] for r in rows][:50]}


OPNAME_MOVES = ["cycle_count_write_off", "cycle_count_adjustment"]


async def step_opname_dead_tags(apply: bool) -> dict:
    """Hanya roll yang keluar stok LEWAT OPNAME (lost_in_count / mutasi opname). Tag aktif pada roll habis karena sebab
    lain (potong/jual) dilaporkan saja (`other`) — wilayah paket RFID (FIX-3b, RFID-2)."""
    ids, other = [], []
    async for t in db.rfid_tags.find({"status": {"$in": ["active", "pending_print"]}, "roll_id": {"$nin": [None, ""]}},
                                     {"_id": 0, "id": 1, "roll_id": 1}):
        r = await db.inventory_rolls.find_one({"id": t["roll_id"]}, {"_id": 0, "status": 1, "length_remaining": 1,
                                                                    "lost_in_count": 1, "reserved_ref": 1})
        gone = r is not None and (r.get("lost_in_count") or (r.get("status") == "consumed"
                                                             and float(r.get("length_remaining") or 0) <= 0.001))
        if not gone or str((r.get("reserved_ref") or {}).get("number") or "") in PROTECTED_ORDERS:
            continue
        by_opname = bool(r.get("lost_in_count")) or bool(await db.inventory_movements.find_one(
            {"roll_id": t["roll_id"], "movement_type": {"$in": OPNAME_MOVES}}, {"_id": 1}))
        if not by_opname:
            other.append(t["id"])
            continue
        ids.append(t["id"])
        if apply:
            await db.rfid_tags.update_one({"id": t["id"], "status": {"$in": ["active", "pending_print"]}},
                                          {"$set": {"status": "retired", "retired_at": now_iso(),
                                                    "retire_reason": "FIX-3a: roll habis/dihapus lewat opname",
                                                    "updated_at": now_iso()}})
            await db.inventory_rolls.update_one({"id": t["roll_id"], "rfid_tag_id": t["id"]},
                                                {"$set": {"rfid_tag_id": None, "tracking_mode": "barcode"}})
    return {"count": len(ids), "ids": ids[:50], "other_report": len(other), "other_ids": other[:20]}


async def step_escalation_posted(apply: bool) -> dict:
    ids = []
    async for t in db.wms_tasks.find({"flow_type": "inbound", "status": "escalated",
                                      "escalation.pre_status": {"$in": ["qc_pending", "qc_rejected", "completed"]}},
                                     {"_id": 0, "id": 1, "escalation": 1}):
        ids.append(t["id"])
        if apply:
            esc = {**(t.get("escalation") or {}), "status": "resolved", "resolved_by": ACTOR, "resolved_at": now_iso(),
                   "resolution_notes": "FIX-3a: eskalasi atas barang yang sudah diposting dikembalikan ke status asalnya"}
            pre = esc.get("pre_status")
            await db.wms_tasks.update_one({"id": t["id"], "status": "escalated"}, {"$set": {
                "status": pre, "escalation": esc, "updated_at": now_iso()},
                "$push": {"status_history": {"status": pre, "timestamp": now_iso(), "user": ACTOR,
                                             "note": "FIX-3a: eskalasi data lama dipulihkan"}}})
    return {"count": len(ids), "ids": ids[:50]}


async def report_over_received() -> dict:
    rows = []
    async for po in db.purchase_orders.find({"items.received_qty": {"$gt": 0}},
                                            {"_id": 0, "id": 1, "po_number": 1, "items": 1, "status": 1}):
        for it in po.get("items") or []:
            q = float(it.get("quantity", it.get("qty", 0)) or 0)
            rec = float(it.get("received_qty") or 0)
            if q > 0 and rec > q * 1.5:
                rows.append({"po_number": po.get("po_number"), "product_id": it.get("product_id"), "qty": q,
                             "received_qty": rec, "status": po.get("status")})
    return {"count": len(rows), "rows": rows[:50]}


async def main() -> None:
    apply = ARGS.apply
    if apply and await db.migrations.find_one({"id": FLAG, "applied": True}):
        print(f"{FLAG} sudah pernah diterapkan — langkah idempoten tetap dijalankan ulang (hanya sisa yang dirapikan).")
    out = {
        "transfer_returned": await step_transfer_returned(apply),
        "transfer_hold": await step_transfer_hold(apply),
        "fake_tag_ref": await step_fake_tag_ref(apply),
        "opname_dead_tags": await step_opname_dead_tags(apply),
        "escalation_posted": await step_escalation_posted(apply),
        "over_received_report": await report_over_received(),
    }
    print(("DITERAPKAN" if apply else "DRY-RUN (tidak ada yang diubah)") + f" — DB {ARGS.db}")
    for k, v in out.items():
        extra = f"  (+{v['other_report']} tag roll habis non-opname, hanya dilaporkan)" if v.get("other_report") else ""
        print(f"  {k:24s} {v['count']:>5}  contoh: {(v.get('ids') or v.get('rows') or [])[:5]}{extra}")
    if apply:
        await db.migrations.update_one({"id": FLAG}, {"$set": {"id": FLAG, "applied": True, "at": now_iso(), "by": ACTOR,
                                                               "result": out}}, upsert=True)


if __name__ == "__main__":
    asyncio.run(main())
