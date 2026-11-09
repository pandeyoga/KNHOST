#!/usr/bin/env python3
"""FIX-3a — rapikan data alur BARANG MASUK yang lahir dari celah yang sudah ditutup kode. DB uji ATAU produksi
(FIX-7: `--production`).

Langkah (semua idempoten; tanpa `--apply` = dry-run: daftar perubahan per dokumen, tidak menulis apa pun):
  1. `transfer_returned`  — transfer `completed` "actual_receipt" padahal 0 roll diterima & ≥1 roll kembali ke asal
                            → status `returned` (keputusan koordinator D10, B2a FLW-IN-10).
  2. `transfer_hold`      — roll berstatus `hold` hasil "diterima ditahan" transfer → `blocked` + `hold{held}` (satu
                            representasi tahan; dilepas lewat Lepas Tahanan) (B2a STM-IN-04). Saldo segmen dibangun ulang.
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
Tidak menyentuh: jurnal/nilai (roll & GL tidak diubah nilainya), data UAT "test" (SORD-261023-0003).
Jejak (FIX-7): per dokumen satu baris `audit_logs` (sebelum/sesudah) + sumber undo di `migrations`
(`fix_data_2026_11_09_fix3a_alur_masuk:changes:<putaran>:<n>`) + ringkasan `migrations.fix_data_2026_11_09_fix3a_alur_masuk`.
`--undo` memulihkan field yang diubah (persis, termasuk yang tadinya tidak ada), mencabut entri riwayat yang ditambahkan,
dan membangun ulang saldo segmen roll yang statusnya dipulihkan — hanya dokumen yang belum diubah orang lain sesudahnya.

Pakai (di dalam kontainer backend, repo = /app) — DB uji:
    python /app/scripts/fix_data_2026_11_09_fix3a_alur_masuk.py --db kn_test_trial            # dry-run (bawaan)
    python /app/scripts/fix_data_2026_11_09_fix3a_alur_masuk.py --db kn_test_trial --apply
    python /app/scripts/fix_data_2026_11_09_fix3a_alur_masuk.py --db kn_test_trial --undo --apply
Produksi: tambah `--db kainnusantara --production --backup-file <kainnusantara-YYYY-MM-DD_HHMM.archive.gz>` —
panduan lengkap `docs/audit/2026-11-09-wms-rfid/hasil/PANDUAN-SKRIP-DATA-PRODUKSI.md`.
"""
import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
from services import data_fix_guard as G  # noqa: E402

FLAG = "fix_data_2026_11_09_fix3a_alur_masuk"
# FIX-7: dulu HANYA `kn_test_trial`; `test_database` (salinan di stack uji) kini juga diterima seperti skrip FIX-1.
ARGS = G.parse_and_guard(G.build_parser(__doc__.splitlines()[0]), FLAG)

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402

ACTOR = "Sistem (FIX-3a rapikan data alur masuk)"
PROTECTED_ORDERS = {"SORD-261023-0003"}   # data UAT "test" — jangan disentuh
APPLY = ARGS.apply


async def step_transfer_returned(P: G.Plan) -> None:
    P.step("transfer_returned", "transfer selesai tanpa roll diterima → returned")
    async for t in db.warehouse_transfers.find({"status": "completed", "completion_basis": "actual_receipt"},
                                               {"_id": 0, "id": 1, "code": 1, "status": 1, "completion_basis": 1,
                                                "updated_at": 1, "fixed_by": 1, "status_history": 1}):
        if await db.inventory_rolls.count_documents({"last_transfer.ref_id": t["id"]}):
            continue
        if not await db.inventory_rolls.count_documents({"returned_from_transfer.ref_id": t["id"]}):
            continue
        now = now_iso()
        before, missing = G.snapshot(t, ("status", "completion_basis", "updated_at", "fixed_by"))
        after = {"status": "returned", "completion_basis": "all_returned", "updated_at": now, "fixed_by": FLAG}
        hist = {"status": "returned", "timestamp": now, "user": ACTOR,
                "note": "data lama: 0 roll diterima, semua kembali ke asal"}
        if APPLY:
            res = await db.warehouse_transfers.update_one({"id": t["id"], "status": "completed"},
                                                          {"$set": after, "$push": {"status_history": hist}})
            if not res.modified_count:
                continue
        P.change("transfer_returned", "warehouse_transfers", t["id"], label=t.get("code") or "", before=before,
                 missing=missing, after=after, pushed={"status_history": hist}, doc=t)


async def step_transfer_hold(P: G.Plan) -> None:
    P.step("transfer_hold", "roll 'hold' transfer → blocked + hold baku")
    ids, segs = [], set()
    async for r in db.inventory_rolls.find({"status": "hold", "last_transfer.outcome": "hold"},
                                           {"_id": 0, "id": 1, "roll_no": 1, "last_transfer": 1, "hold": 1, "status": 1,
                                            "updated_at": 1, "product_id": 1, "warehouse_id": 1, "owner_entity_id": 1,
                                            "hold_history": 1}):
        ids.append(r["id"])
        lt = r.get("last_transfer") or {}
        now = now_iso()
        before, missing = G.snapshot(r, ("status", "updated_at", "hold"))
        after = {"status": "blocked", "updated_at": now,
                 "hold": {"held": True, "reason": f"Diterima dengan pengecualian aturan gudang (transfer {lt.get('code') or ''})",
                          "by": lt.get("received_by") or ACTOR, "at": lt.get("date") or now,
                          "prev_status": "available", "source": "transfer_rule"}}
        hist = {"action": "hold", "reason": "FIX-3a: status 'hold' transfer → tahan baku", "by": ACTOR, "at": now,
                "status_from": "hold", "status_to": "blocked"}
        seg = (r.get("product_id"), r.get("warehouse_id"), r.get("owner_entity_id"))
        if APPLY:
            res = await db.inventory_rolls.update_one({"id": r["id"], "status": "hold"},
                                                      {"$set": after, "$push": {"hold_history": hist}})
            if not res.modified_count:
                continue
        P.change("transfer_hold", "inventory_rolls", r["id"], label=r.get("roll_no") or "", before=before,
                 missing=missing, after=after, pushed={"hold_history": hist}, segment=seg, doc=r)
    if APPLY and ids:
        from services.roll_service import rebuild_balance
        async for r in db.inventory_rolls.find({"id": {"$in": ids}}, {"_id": 0, "product_id": 1, "warehouse_id": 1,
                                                                      "owner_entity_id": 1}):
            k = (r["product_id"], r["warehouse_id"], r.get("owner_entity_id"))
            if k not in segs:
                segs.add(k)
                await rebuild_balance(*k)


async def step_fake_tag_ref(P: G.Plan) -> None:
    P.step("fake_tag_ref", "Roll ID teks bebas di rfid_tag_id → supplier_roll_no")
    async for r in db.inventory_rolls.find({"acquired.via": "inbound", "rfid_tag_id": {"$nin": [None, ""]}},
                                           {"_id": 0, "id": 1, "roll_no": 1, "rfid_tag_id": 1, "supplier_roll_no": 1,
                                            "updated_at": 1, "fixed_by": 1, "legacy_roll_id_input": 1}):
        if await db.rfid_tags.find_one({"id": r["rfid_tag_id"]}, {"_id": 1}):
            continue
        upd = {"rfid_tag_id": None, "updated_at": now_iso(), "fixed_by": FLAG, "legacy_roll_id_input": r["rfid_tag_id"]}
        if not r.get("supplier_roll_no"):
            upd["supplier_roll_no"] = str(r["rfid_tag_id"]).strip()
        before, missing = G.snapshot(r, tuple(upd))
        if APPLY:
            res = await db.inventory_rolls.update_one({"id": r["id"], "rfid_tag_id": r["rfid_tag_id"]}, {"$set": upd})
            if not res.modified_count:
                continue
        P.change("fake_tag_ref", "inventory_rolls", r["id"], label=r.get("roll_no") or "", before=before,
                 missing=missing, after=upd)


OPNAME_MOVES = ["cycle_count_write_off", "cycle_count_adjustment"]


async def step_opname_dead_tags(P: G.Plan) -> None:
    """Hanya roll yang keluar stok LEWAT OPNAME (lost_in_count / mutasi opname). Tag aktif pada roll habis karena sebab
    lain (potong/jual) dilaporkan saja (`other`) — wilayah paket RFID (FIX-3b, RFID-2)."""
    P.step("opname_dead_tags", "tag aktif pada roll habis lewat opname → retired")
    other = []
    async for t in db.rfid_tags.find({"status": {"$in": ["active", "pending_print"]}, "roll_id": {"$nin": [None, ""]}},
                                     {"_id": 0, "id": 1, "epc": 1, "roll_id": 1, "status": 1, "retired_at": 1,
                                      "retire_reason": 1, "updated_at": 1}):
        r = await db.inventory_rolls.find_one({"id": t["roll_id"]}, {"_id": 0, "status": 1, "length_remaining": 1,
                                                                    "lost_in_count": 1, "reserved_ref": 1, "roll_no": 1,
                                                                    "rfid_tag_id": 1, "tracking_mode": 1})
        gone = r is not None and (r.get("lost_in_count") or (r.get("status") == "consumed"
                                                             and float(r.get("length_remaining") or 0) <= 0.001))
        if not gone or str((r.get("reserved_ref") or {}).get("number") or "") in PROTECTED_ORDERS:
            continue
        by_opname = bool(r.get("lost_in_count")) or bool(await db.inventory_movements.find_one(
            {"roll_id": t["roll_id"], "movement_type": {"$in": OPNAME_MOVES}}, {"_id": 1}))
        if not by_opname:
            other.append(t["id"])
            continue
        now = now_iso()
        t_after = {"status": "retired", "retired_at": now, "retire_reason": "FIX-3a: roll habis/dihapus lewat opname",
                   "updated_at": now}
        t_before, t_missing = G.snapshot(t, tuple(t_after))
        if APPLY:
            res = await db.rfid_tags.update_one({"id": t["id"], "status": {"$in": ["active", "pending_print"]}},
                                                {"$set": t_after})
            if not res.modified_count:
                continue
        P.change("opname_dead_tags", "rfid_tags", t["id"], label=f"EPC {t.get('epc') or ''} · roll {r.get('roll_no') or ''}",
                 before=t_before, missing=t_missing, after=t_after)
        if r.get("rfid_tag_id") == t["id"]:
            r_after = {"rfid_tag_id": None, "tracking_mode": "barcode"}
            r_before, r_missing = G.snapshot(r, tuple(r_after))
            if APPLY:
                res = await db.inventory_rolls.update_one({"id": t["roll_id"], "rfid_tag_id": t["id"]}, {"$set": r_after})
                if not res.modified_count:
                    continue
            P.change("opname_dead_tags", "inventory_rolls", t["roll_id"], label=r.get("roll_no") or "",
                     before=r_before, missing=r_missing, after=r_after, note="tag dilepas dari roll")
    P.report_only("opname_dead_tags_other", {"count": len(other), "ids": other[:50]},
                  "tag aktif pada roll habis BUKAN lewat opname — hanya dilaporkan (wilayah FIX-3b/RFID-2)")


async def step_escalation_posted(P: G.Plan) -> None:
    P.step("escalation_posted", "eskalasi atas barang yang sudah diposting → status asal")
    async for t in db.wms_tasks.find({"flow_type": "inbound", "status": "escalated",
                                      "escalation.pre_status": {"$in": ["qc_pending", "qc_rejected", "completed"]}},
                                     {"_id": 0, "id": 1, "code": 1, "task_number": 1, "status": 1, "escalation": 1,
                                      "updated_at": 1, "status_history": 1}):
        now = now_iso()
        esc = {**(t.get("escalation") or {}), "status": "resolved", "resolved_by": ACTOR, "resolved_at": now,
               "resolution_notes": "FIX-3a: eskalasi atas barang yang sudah diposting dikembalikan ke status asalnya"}
        pre = esc.get("pre_status")
        before, missing = G.snapshot(t, ("status", "escalation", "updated_at"))
        after = {"status": pre, "escalation": esc, "updated_at": now}
        hist = {"status": pre, "timestamp": now, "user": ACTOR, "note": "FIX-3a: eskalasi data lama dipulihkan"}
        if APPLY:
            res = await db.wms_tasks.update_one({"id": t["id"], "status": "escalated"},
                                                {"$set": after, "$push": {"status_history": hist}})
            if not res.modified_count:
                continue
        P.change("escalation_posted", "wms_tasks", t["id"], label=t.get("task_number") or t.get("code") or "",
                 before=before, missing=missing, after=after, pushed={"status_history": hist}, doc=t)


async def report_over_received(P: G.Plan) -> None:
    rows = []
    async for po in db.purchase_orders.find({"items.received_qty": {"$gt": 0}},
                                            {"_id": 0, "id": 1, "po_number": 1, "items": 1, "status": 1}):
        for it in po.get("items") or []:
            q = float(it.get("quantity", it.get("qty", 0)) or 0)
            rec = float(it.get("received_qty") or 0)
            if q > 0 and rec > q * 1.5:
                rows.append({"po_number": po.get("po_number"), "product_id": it.get("product_id"), "qty": q,
                             "received_qty": rec, "status": po.get("status")})
    P.report_only("over_received_report", {"count": len(rows), "rows": rows[:50]},
                  "baris PO diterima > 1,5× pesanan — tinjau pembelian/finance")


async def forward(P: G.Plan) -> None:
    if APPLY and await db.migrations.find_one({"id": FLAG, "applied": True}):
        print(f"{FLAG} sudah pernah diterapkan — langkah idempoten tetap dijalankan ulang (hanya sisa yang dirapikan).")
    await step_transfer_returned(P)
    await step_transfer_hold(P)
    await step_fake_tag_ref(P)
    await step_opname_dead_tags(P)
    await step_escalation_posted(P)
    await report_over_received(P)
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
        rev_after = {**c["before"], **{f: None for f in c["missing"]}}
        if APPLY:
            if not await G.apply_restore(db, c):
                print(f"  LEWAT {c['collection']} {c['doc_id']} ({c['step']}): sudah diubah sesudah skrip — tidak dikembalikan.")
                continue
        P.change(step, c["collection"], c["doc_id"], label=c.get("label", ""), before=c["after"], after=rev_after)
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
