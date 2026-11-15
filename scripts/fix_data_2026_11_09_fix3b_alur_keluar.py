#!/usr/bin/env python3
"""FIX-3b — rapikan data alur BARANG KELUAR, potong & RFID yang lahir dari celah yang sudah ditutup kode. DB uji ATAU
produksi (FIX-7: `--production`).

Langkah (semua idempoten; tanpa `--apply` = dry-run: daftar perubahan per dokumen, tidak menulis apa pun):
  1. `rfid_simulation_off` — Mode simulasi RFID (`wms.rfid_simulation`) yang MENYALA untuk PT nyata (ent_ksc, ent_kanda,
                             ent_82b52ed6ee8b) → dimatikan (catatan pra-pilot B2b RFID-9, keputusan K-B2b-09).
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
Tidak menyentuh: jurnal (saldo segmen yang rolnya berubah dibangun ulang), data UAT "test" (SORD-261023-0003).
Catatan dry-run: tiap langkah dihitung atas data SEKARANG; saat --apply langkah berikut melihat hasil langkah sebelumnya
(mis. roll yang dipulihkan langkah 2 bisa ikut langkah 4), jadi jumlah --apply bisa sedikit berbeda dari dry-run.
Jejak (FIX-7): per dokumen satu baris `audit_logs` (sebelum/sesudah) + sumber undo di `migrations`
(`fix_data_2026_11_09_fix3b_alur_keluar:changes:<putaran>:<n>`). `--undo` memulihkan field yang diubah (persis), menghapus
mutasi `release_reservation` yang DISISIPKAN putaran itu, dan membangun ulang saldo segmen roll terkait — hanya dokumen
yang belum diubah orang lain sesudahnya.

Pakai (di dalam kontainer backend, repo = /app) — DB uji:
    python /app/scripts/fix_data_2026_11_09_fix3b_alur_keluar.py --db kn_test_trial            # dry-run (bawaan)
    python /app/scripts/fix_data_2026_11_09_fix3b_alur_keluar.py --db kn_test_trial --apply
    python /app/scripts/fix_data_2026_11_09_fix3b_alur_keluar.py --db kn_test_trial --undo --apply
Produksi: tambah `--db kainnusantara --production --backup-file <kainnusantara-YYYY-MM-DD_HHMM.archive.gz>` —
panduan lengkap `docs/audit/2026-11-09-wms-rfid/hasil/PANDUAN-SKRIP-DATA-PRODUKSI.md`.
"""
import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
from services import data_fix_guard as G  # noqa: E402

FLAG = "fix_data_2026_11_09_fix3b_alur_keluar"
# FIX-7: dulu HANYA `kn_test_trial`; `test_database` (salinan di stack uji) kini juga diterima seperti skrip FIX-1.
ARGS = G.parse_and_guard(G.build_parser(__doc__.splitlines()[0]), FLAG)

from core_utils import new_id, now_iso  # noqa: E402
from db import db  # noqa: E402

ACTOR = "Sistem (FIX-3b rapikan data alur keluar)"
PROTECTED_ORDERS = {"SORD-261023-0003"}   # data UAT "test" — jangan disentuh
REAL_PT = ("ent_ksc", "ent_kanda", "ent_82b52ed6ee8b")
SO_DEAD = ("cancelled", "expired", "done", "rejected", "draft")
SEGMENTS: set = set()
APPLY = ARGS.apply
ROLL_PROJ = {"_id": 0, "id": 1, "roll_no": 1, "product_id": 1, "warehouse_id": 1, "owner_entity_id": 1, "status": 1,
             "reserved_ref": 1, "updated_at": 1, "fix3b_note": 1, "delivered_at": 1, "delivered_via": 1}


def _seg(r: dict) -> tuple:
    return (r.get("product_id"), r.get("warehouse_id"), r.get("owner_entity_id"))


async def _protected_so_ids() -> set:
    return {o["id"] async for o in db.sales_orders.find(
        {"$or": [{"number": {"$in": list(PROTECTED_ORDERS)}}, {"order_number": {"$in": list(PROTECTED_ORDERS)}}]},
        {"_id": 0, "id": 1})}


async def step_rfid_simulation_off(P: G.Plan) -> None:
    P.step("rfid_simulation_off", "mode simulasi RFID PT nyata/global → mati")
    async for c in db.config_values.find({"key": "wms.rfid_simulation", "value": True,
                                          "$or": [{"scope_type": "entity", "scope_id": {"$in": list(REAL_PT)}},
                                                  {"scope_type": "global"}]}, {"_id": 0}):
        after = {"value": False, "updated_at": now_iso(), "updated_by": ACTOR,
                 "note": "FIX-3b (B2b RFID-9): mode simulasi dimatikan sebelum reader nyata dipasang"}
        before, missing = G.snapshot(c, tuple(after))
        if APPLY:
            res = await db.config_values.update_one({"id": c.get("id"), "key": "wms.rfid_simulation"}, {"$set": after})
            if not res.modified_count:
                continue
        P.change("rfid_simulation_off", "config_values", c.get("id"),
                 label=f"{c.get('scope_type')}:{c.get('scope_id') or '-'}", before=before, missing=missing, after=after)


async def step_shipped_roll_released(P: G.Plan, protected: set) -> None:
    P.step("shipped_roll_released", "roll di SJ aktif tetapi 'available' → in_transit_sales/delivered")
    seen = set()
    async for s in db.shipments.find({"status": {"$nin": ["cancelled", "void", "voided"]}},
                                     {"_id": 0, "id": 1, "order_id": 1, "rolls.roll_id": 1, "logistics_status": 1}):
        if s.get("order_id") in protected:
            continue
        rids = [r.get("roll_id") for r in s.get("rolls") or [] if r.get("roll_id")]
        if not rids:
            continue
        async for r in db.inventory_rolls.find({"id": {"$in": rids}, "status": "available"}, ROLL_PROJ):
            if r["id"] in seen:   # dry-run: roll di >1 SJ hanya dihitung sekali (saat --apply SJ kedua tak menemukannya)
                continue
            seen.add(r["id"])
            to = "delivered" if s.get("logistics_status") in ("delivered", "completed") else "in_transit_sales"
            after = {"status": to, "reserved_ref": {"type": "sales_order", "id": s["order_id"]}, "updated_at": now_iso(),
                     "fix3b_note": f"dipulihkan dari SJ {s['id']} (STM-OUT-1)"}
            before, missing = G.snapshot(r, tuple(after))
            if APPLY:
                res = await db.inventory_rolls.update_one({"id": r["id"], "status": "available"}, {"$set": after})
                if not res.modified_count:
                    continue
                SEGMENTS.add(_seg(r))
            P.change("shipped_roll_released", "inventory_rolls", r["id"], label=r.get("roll_no") or "", before=before,
                     missing=missing, after=after, segment=_seg(r))


async def step_dead_so_reservations(P: G.Plan, protected: set) -> None:
    P.step("dead_so_reservations", "reservasi milik SO terminal/draf → available + mutasi release_reservation")
    dead = {o["id"] async for o in db.sales_orders.find({"status": {"$in": list(SO_DEAD)}}, {"_id": 0, "id": 1})} - protected
    async for r in db.inventory_rolls.find({"reserved_ref.type": "sales_order", "reserved_ref.id": {"$in": list(dead)},
                                            "status": {"$in": ["reserved", "committed", "picked", "packed"]}},
                                           {"_id": 0}):
        after = {"status": "available", "reserved_ref": None, "updated_at": now_iso()}
        before, missing = G.snapshot(r, tuple(after))
        mov = {"id": new_id("mov"), "product_id": r["product_id"], "warehouse_id": r["warehouse_id"],
               "owner_entity_id": r.get("owner_entity_id"), "movement_type": "release_reservation",
               "quantity": round(float(r.get("length_remaining") or 0), 2), "unit": r.get("unit", "meter"),
               "lot": r.get("lot", ""), "roll_id": r["id"], "qty_rolls": 1,
               "source_document": r["reserved_ref"]["id"], "timestamp": now_iso(),
               "note": "FIX-3b: reservasi milik SO terminal/draf dilepas (STM-OUT-4)"}
        if APPLY:
            res = await db.inventory_rolls.update_one({"id": r["id"], "status": r["status"]}, {"$set": after})
            if not res.modified_count:
                continue
            await db.inventory_movements.insert_one(dict(mov))
            SEGMENTS.add(_seg(r))
        P.change("dead_so_reservations", "inventory_rolls", r["id"], label=r.get("roll_no") or "", before=before,
                 missing=missing, after=after, inserted={"collection": "inventory_movements", "id": mov["id"]},
                 segment=_seg(r), note=f"SO {r['reserved_ref'].get('number') or r['reserved_ref']['id']}")


async def step_pod_rolls(P: G.Plan, protected: set) -> None:
    P.step("pod_rolls_in_transit", "roll in_transit_sales pada SJ ber-POD → delivered")
    seen = set()
    async for s in db.shipments.find({"status": {"$nin": ["cancelled", "void", "voided"]},
                                      "logistics_status": {"$in": ["delivered", "completed"]}},
                                     {"_id": 0, "id": 1, "order_id": 1, "rolls.roll_id": 1}):
        if s.get("order_id") in protected:
            continue
        rids = [r.get("roll_id") for r in s.get("rolls") or [] if r.get("roll_id")]
        async for r in db.inventory_rolls.find({"id": {"$in": rids}, "status": "in_transit_sales"}, ROLL_PROJ):
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            now = now_iso()
            after = {"status": "delivered", "delivered_at": now, "delivered_via": "fix3b_pod_per_sj", "updated_at": now}
            before, missing = G.snapshot(r, tuple(after))
            if APPLY:
                res = await db.inventory_rolls.update_one({"id": r["id"], "status": "in_transit_sales"}, {"$set": after})
                if not res.modified_count:
                    continue
                SEGMENTS.add(_seg(r))
            P.change("pod_rolls_in_transit", "inventory_rolls", r["id"], label=r.get("roll_no") or "", before=before,
                     missing=missing, after=after, segment=_seg(r))


async def step_escalation_on_terminal(P: G.Plan) -> None:
    P.step("escalation_on_terminal", "eskalasi pada tugas batal/terkirim → cancelled")
    async for t in db.wms_tasks.find({"flow_type": "outbound", "status": {"$in": ["cancelled", "dispatched"]},
                                      "escalation.status": {"$in": ["pending_review", "resolving"]}},
                                     {"_id": 0, "id": 1, "task_number": 1, "escalation": 1}):
        after = {"escalation.status": "cancelled", "escalation.cancelled_at": now_iso(),
                 "escalation.resolution_notes": "FIX-3b: eskalasi atas tugas terminal ditutup (STM-OUT-2)"}
        before, missing = G.snapshot(t, tuple(after))
        if APPLY:
            res = await db.wms_tasks.update_one({"id": t["id"]}, {"$set": after})
            if not res.modified_count:
                continue
        P.change("escalation_on_terminal", "wms_tasks", t["id"], label=t.get("task_number") or "", before=before,
                 missing=missing, after=after)


async def step_stale_transfer_marker(P: G.Plan) -> None:
    P.step("stale_transfer_marker", "transfer_prior_status basi → kosong")
    async for r in db.inventory_rolls.find({"transfer_prior_status": {"$nin": [None, ""]},
                                            "status": {"$nin": ["in_transit_transfer"]},
                                            "reserved_ref.type": {"$ne": "wh_transfer"},
                                            "transfer_ref": {"$in": [None, {}]}},
                                           {"_id": 0, "id": 1, "roll_no": 1, "transfer_prior_status": 1}):
        after = {"transfer_prior_status": None}
        before, missing = G.snapshot(r, tuple(after))
        if APPLY:
            res = await db.inventory_rolls.update_one({"id": r["id"]}, {"$set": after})
            if not res.modified_count:
                continue
        P.change("stale_transfer_marker", "inventory_rolls", r["id"], label=r.get("roll_no") or "", before=before,
                 missing=missing, after=after)


async def step_consumed_revived(P: G.Plan) -> None:
    P.step("consumed_revived", "roll 'available' panjang 0 ber-consumed_ref → consumed")
    async for r in db.inventory_rolls.find({"status": "available", "consumed_ref": {"$nin": [None, ""]},
                                            "length_remaining": {"$lte": 0}}, ROLL_PROJ):
        after = {"status": "consumed", "updated_at": now_iso(), "fix3b_note": "MKO-03: roll habis dihidupkan retur bahan"}
        before, missing = G.snapshot(r, tuple(after))
        if APPLY:
            res = await db.inventory_rolls.update_one({"id": r["id"], "status": "available"}, {"$set": after})
            if not res.modified_count:
                continue
            SEGMENTS.add(_seg(r))
        P.change("consumed_revived", "inventory_rolls", r["id"], label=r.get("roll_no") or "", before=before,
                 missing=missing, after=after, segment=_seg(r))


async def step_sample_paid_cancelled(P: G.Plan, protected: set) -> None:
    P.step("sample_paid_cancelled", "SO sampel berbayar batal → refund_pending")
    async for o in db.sales_orders.find({"status": "cancelled", "sample_billing": "paid",
                                         "sample_payment_status": "approved"},
                                        {"_id": 0, "id": 1, "number": 1, "sample_payment_status": 1,
                                         "sample_payment_cancel_reason": 1}):
        if o["id"] in protected:
            continue
        after = {"sample_payment_status": "refund_pending", "sample_payment_cancel_reason": "FIX-3b: SO sampel batal (CUT-6)"}
        before, missing = G.snapshot(o, tuple(after))
        if APPLY:
            res = await db.sales_orders.update_one({"id": o["id"], "sample_payment_status": "approved"}, {"$set": after})
            if not res.modified_count:
                continue
        P.change("sample_paid_cancelled", "sales_orders", o["id"], label=o.get("number") or "", before=before,
                 missing=missing, after=after)


async def report_epc_reuse(P: G.Plan) -> None:
    rows = []
    async for g in db.rfid_tags.aggregate([{"$group": {"_id": "$epc", "n": {"$sum": 1}, "rolls": {"$addToSet": "$roll_id"},
                                                       "statuses": {"$push": "$status"}}},
                                           {"$match": {"n": {"$gt": 1}}}]):
        if len(g.get("rolls") or []) > 1:
            rows.append({"epc": g["_id"], "rolls": g["rolls"][:5], "statuses": g["statuses"][:5]})
    P.report_only("epc_reuse_report", {"count": len(rows), "rows": rows[:50]},
                  "EPC dipakai >1 tag — cek fisik, tidak diubah otomatis")


async def forward(P: G.Plan) -> None:
    if APPLY and await db.migrations.find_one({"id": FLAG, "applied": True}):
        print(f"{FLAG} sudah pernah diterapkan — langkah idempoten tetap dijalankan ulang (hanya sisa yang dirapikan).")
    protected = await _protected_so_ids()
    await step_rfid_simulation_off(P)
    await step_shipped_roll_released(P, protected)
    await step_dead_so_reservations(P, protected)
    await step_pod_rolls(P, protected)
    await step_escalation_on_terminal(P)
    await step_stale_transfer_marker(P)
    await step_consumed_revived(P)
    await step_sample_paid_cancelled(P, protected)
    await report_epc_reuse(P)
    if APPLY and SEGMENTS:
        from services.roll_service import rebuild_balance
        for p, w, o in SEGMENTS:
            await rebuild_balance(p, w, o)
        print(f"   saldo dibangun ulang: {len(SEGMENTS)} segmen")
    if APPLY:
        await db.migrations.update_one({"id": FLAG}, {"$set": {
            "id": FLAG, "applied": True, "at": now_iso(), "by": ACTOR,
            "result": {k: v["count"] for k, v in P.steps.items()}}}, upsert=True)


async def undo(P: G.Plan) -> str:
    try:
        rid, changes = await G.load_run(db, FLAG, ARGS.run_id)
    except G.Refused as exc:
        G.print_refusal_and_exit(exc)
    if not rid:
        print("Tidak ada putaran --apply berjejak (FIX-7) yang belum dibalik. Putaran sebelum FIX-7 tidak punya nilai "
              "sebelum → tidak bisa dibalik otomatis (pulihkan dari backup bila perlu).")
        return ""
    print(f"   membalik putaran {rid}: {len(changes)} perubahan")
    segs = set()
    for c in reversed(changes):
        step = c["step"] + "_undo"
        P.step(step)
        if c["collection"] == "config_values" and c["doc_id"] is None:
            print(f"  LEWAT config_values tanpa id ({c.get('label')}): pulihkan manual dari Pusat Pengaturan.")
            continue
        rev_after = {**c["before"], **{f: None for f in c["missing"]}}
        ins = c.get("inserted") or {}
        if APPLY:
            if not await G.apply_restore(db, c):
                print(f"  LEWAT {c['collection']} {c['doc_id']} ({c['step']}): sudah diubah sesudah skrip — tidak dikembalikan.")
                continue
            if ins.get("id"):
                await db[ins["collection"]].delete_one({"id": ins["id"], "roll_id": c["doc_id"],
                                                        "movement_type": "release_reservation"})
        P.change(step, c["collection"], c["doc_id"], label=c.get("label", ""), before=c["after"], after=rev_after,
                 note=f"hapus mutasi {ins['id']}" if ins.get("id") else "")
        if c.get("segment"):
            segs.add(tuple(c["segment"]))
    if APPLY and segs:
        from services.roll_service import rebuild_balance
        for k in segs:
            await rebuild_balance(*k)
        print(f"   saldo dibangun ulang: {len(segs)} segmen")
    return rid


async def main() -> None:
    G.banner(ARGS)
    P = G.Plan(ARGS)
    undone = ""
    if ARGS.undo:
        undone = await undo(P)
    else:
        await forward(P)
    P.print()
    P.write_report()
    if APPLY and P.changes:
        await P.save(db, ACTOR, kind="undo" if ARGS.undo else "apply", undone_run=undone)
    print(("DITERAPKAN" if APPLY else "DRY-RUN (tidak ada yang diubah)") + f" — DB {ARGS.db}: {len(P.changes)} perubahan dokumen")
    await G.drain_tasks()


if __name__ == "__main__":
    asyncio.run(main())
