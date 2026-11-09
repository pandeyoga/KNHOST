"""FIX-2 (audit B3a SSOT-3, keputusan koordinator #2) — selaraskan roll yang DITAHAN inspeksi (MD Quality / 4-point,
`inspection.hold.held=true`) tetapi statusnya masih `available`/`quarantine` → status `blocked` lewat
`roll_hold_service.sync_inspection_hold` (+ rebuild saldo). Sesudah FIX-2 penahanan baru langsung memakai jalur itu;
skrip ini hanya untuk data lama. BAWAAN = dry-run (tidak menulis apa pun).

FIX-7 — pagar DB uji ↔ produksi (`services/data_fix_guard.py`): `--db` bawaan = `DB_NAME` lingkungan (perintah lama
tetap jalan di DB uji `test_database`/`kn_test_trial`); DB produksi `kainnusantara` wajib `--production` + bukti backup
< 24 jam; DB lain ditolak (dulu skrip ini menulis ke DB mana pun yang ditunjuk `DB_NAME`). `--apply` mencatat jejak per
roll (`audit_logs` + `migrations`), `--undo` memulihkan status/tahan sebelum (+ cabut entri riwayat, rebuild saldo).

Pakai (di dalam kontainer backend):
  python /app/backend/scripts/migrate_fix2_inspection_hold_status.py            # dry-run: daftar kandidat
  python /app/backend/scripts/migrate_fix2_inspection_hold_status.py --apply    # tulis
  python /app/backend/scripts/migrate_fix2_inspection_hold_status.py --undo --apply
Produksi: `… --db kainnusantara --production --backup-file <kainnusantara-YYYY-MM-DD_HHMM.archive.gz> [--apply]` —
panduan lengkap `docs/audit/2026-11-09-wms-rfid/hasil/PANDUAN-SKRIP-DATA-PRODUKSI.md`.
Data acuan 9 Nov 2026: 0 kandidat (B3a C.6 "inspection.hold.held=true · 0").
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from services import data_fix_guard as G  # noqa: E402

FLAG = "migrate_fix2_inspection_hold_status"
ACTOR = "Migrasi FIX-2"


def _args():
    ap = G.build_parser(__doc__.splitlines()[0], db_default=os.environ.get("DB_NAME", ""))
    return G.parse_and_guard(ap, FLAG)


async def forward(args, P) -> None:
    from db import db
    from services.roll_hold_service import HOLDABLE_STATUSES, sync_inspection_hold
    P.step("inspection_hold_blocked", "roll ditahan inspeksi berstatus available/quarantine → blocked")
    q = {"inspection.hold.held": True, "status": {"$in": list(HOLDABLE_STATUSES)}}
    rows = await db.inventory_rolls.find(q, {"_id": 0, "id": 1, "roll_no": 1, "status": 1, "earmarked_for": 1, "hold": 1,
                                             "updated_at": 1, "product_id": 1, "warehouse_id": 1,
                                             "owner_entity_id": 1, "hold_history": 1,
                                             "status_history": 1}).to_list(None)
    print(f"kandidat: {len(rows)} roll (mode {'APPLY' if args.apply else 'dry-run'})")
    for r in rows:
        if r.get("earmarked_for"):
            print(f"  {r.get('roll_no')} {r['id']} status={r.get('status')} (dilewati: di-peg pelanggan)")
            continue
        # FIX-10: perubahan status lewat `roll_state` menambah `status_history` — ikut direkam supaya `--undo` memulihkan
        # roll PERSIS (dikembalikan bila dulu ada, dihapus bila dulu tidak ada).
        before, missing = G.snapshot(r, ("status", "hold", "updated_at", "status_history"))
        seg = (r.get("product_id"), r.get("warehouse_id"), r.get("owner_entity_id"))
        if not args.apply:
            P.change("inspection_hold_blocked", "inventory_rolls", r["id"], label=r.get("roll_no") or "",
                     before=before, missing=missing, after={"status": "blocked", "hold": "{held, source: inspection}"},
                     segment=seg)
            continue
        if not await sync_inspection_hold(r["id"], {"name": ACTOR}):
            continue
        cur = await db.inventory_rolls.find_one({"id": r["id"]}, {"_id": 0, "status": 1, "hold": 1, "updated_at": 1,
                                                                 "hold_history": {"$slice": -1}})
        pushed = {"hold_history": (cur.get("hold_history") or [None])[-1]} if cur.get("hold_history") else {}
        P.change("inspection_hold_blocked", "inventory_rolls", r["id"], label=r.get("roll_no") or "", before=before,
                 missing=missing, after={k: cur.get(k) for k in ("status", "hold", "updated_at")}, pushed=pushed,
                 segment=seg, doc=r)


async def undo(args, P) -> str:
    from db import db
    from services.roll_service import rebuild_balance
    try:
        rid, changes = await G.load_run(db, FLAG, args.run_id)
    except G.Refused as exc:
        G.print_refusal_and_exit(exc)
    if not rid:
        print("Tidak ada putaran --apply berjejak (FIX-7) yang belum dibalik.")
        return ""
    P.step("inspection_hold_blocked_undo", "status & tahan sebelum dipulihkan")
    segs = set()
    for c in reversed(changes):
        rev = {**c["before"], **{f: None for f in c["missing"]}}
        if args.apply:
            if not await G.apply_restore(db, c):
                print(f"  LEWAT {c.get('label') or c['doc_id']}: roll sudah diubah sesudah migrasi — tidak dikembalikan.")
                continue
        P.change("inspection_hold_blocked_undo", "inventory_rolls", c["doc_id"], label=c.get("label", ""),
                 before=c["after"], after=rev)
        if c.get("segment"):
            segs.add(tuple(c["segment"]))
    if args.apply:
        for k in segs:
            await rebuild_balance(*k)
    return rid


async def main(args) -> int:
    from db import db
    G.banner(args)
    P = G.Plan(args)
    undone = await undo(args, P) if args.undo else await forward(args, P)
    P.print()
    P.write_report()
    if args.apply and P.changes:
        await P.save(db, ACTOR, kind="undo" if args.undo else "apply", undone_run=undone or "")
    if args.apply:
        print(f"diubah: {len(P.changes)}")
    await G.drain_tasks()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(_args())))
