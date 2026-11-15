#!/usr/bin/env python3
"""FIX-1 (K-GDG-07, B2a FLW-IN-07/FLW-IN-20, B1 K-B1-02) — gedung KHUSUS PT yang bertentangan dengan keputusan pemilik
"semua gedung dipakai bersama semua PT" diubah menjadi BERSAMA. DB uji ATAU produksi (FIX-7: `--production`).

Data acuan (snapshot 8 Nov): `SRG-01` (Soreang · Gudang Kanda, khusus Kanda) dan `WH-JKT` (Jakarta, khusus Sukacita)
masih `dedicated` → PO PT lain ke Soreang ditolak, tugas PT lain di gedung yang sama tidak bisa dibuat.

Yang diubah: gedung AKTIF ber-`sharing_mode: dedicated`, BUKAN data uji (`is_test`, kode `TEST-…`, nama `TEST_…`).
Gedung nonaktif (WH-BDG, GU-*) & gedung uji dilewati. Mengubah khusus → bersama tidak pernah mengurung stok (pagar
`dedication_blockers` hanya untuk arah sebaliknya). Yang TIDAK disentuh: stok, roll, bin, aturan simpan, gate.

Jejak & pembalik (FIX-7): per gedung satu baris `audit_logs` (sebelum/sesudah) + sumber undo di `migrations`
(`fix_data_2026_11_09_gedung_bersama:changes:<putaran>:<n>`); `--undo` mengembalikan nilai sebelum (hanya bila gedung
belum diubah orang lain sesudahnya). Jejak format lama (`runs[].changes`, sebelum FIX-7) tetap bisa dibalik.

Pakai (di dalam kontainer backend, repo = /app) — DB uji:
    python /app/scripts/fix_data_2026_11_09_gedung_bersama.py --db kn_test_trial            # dry-run (bawaan)
    python /app/scripts/fix_data_2026_11_09_gedung_bersama.py --db kn_test_trial --apply
    python /app/scripts/fix_data_2026_11_09_gedung_bersama.py --db kn_test_trial --undo --apply
Produksi: tambah `--db kainnusantara --production --backup-file <kainnusantara-YYYY-MM-DD_HHMM.archive.gz>` —
panduan lengkap `docs/audit/2026-11-09-wms-rfid/hasil/PANDUAN-SKRIP-DATA-PRODUKSI.md`.
"""
import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
from services import data_fix_guard as G  # noqa: E402

FLAG = "fix_data_2026_11_09_gedung_bersama"
ARGS = G.parse_and_guard(G.build_parser(__doc__.splitlines()[0]), FLAG)

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402

ACTOR = "Sistem (K-GDG-07 gedung dipakai bersama)"
FIELDS = ("sharing_mode", "entity_ids", "updated_at")


def is_test_warehouse(w: dict) -> bool:
    code, name = str(w.get("code") or ""), str(w.get("name") or "")
    return bool(w.get("is_test")) or code.upper().startswith("TEST-") or name.upper().startswith("TEST_")


async def plan() -> list:
    rows = []
    async for w in db.warehouses.find({"active": {"$ne": False}, "sharing_mode": "dedicated"}, {"_id": 0}).sort("code", 1):
        if is_test_warehouse(w):
            continue
        rows.append(w)
    return rows


async def apply_forward(P: G.Plan) -> None:
    P.step("gedung_bersama", "gedung khusus PT → bersama")
    for w in await plan():
        before, missing = G.snapshot(w, FIELDS)
        after = {"sharing_mode": "shared", "entity_ids": [], "updated_at": now_iso()}
        label = f"{w.get('code', '')} {str(w.get('name', ''))[:40]}".strip()
        if not ARGS.apply:
            P.change("gedung_bersama", "warehouses", w["id"], label=label, before=before, missing=missing, after=after)
            continue
        res = await db.warehouses.update_one({"id": w["id"], "sharing_mode": "dedicated", "updated_at": w.get("updated_at")},
                                             {"$set": after})
        if not res.modified_count:
            print(f"  LEWAT {w.get('code')}: gedung berubah bersamaan — jalankan ulang skrip.")
            continue
        P.change("gedung_bersama", "warehouses", w["id"], label=label, before=before, missing=missing, after=after)


async def _legacy_changes() -> list:
    """Jejak format lama (sebelum FIX-7): migrations.<FLAG>.runs[].changes {warehouse_id, code, before}."""
    mig = await db.migrations.find_one({"id": FLAG}, {"_id": 0, "runs": 1}) or {}
    return [c for run in mig.get("runs") or [] for c in run.get("changes") or []]


async def apply_undo(P: G.Plan) -> str:
    P.step("gedung_bersama_undo", "kembalikan khusus PT")
    try:
        rid, changes = await G.load_run(db, FLAG, ARGS.run_id)
    except G.Refused as exc:
        G.print_refusal_and_exit(exc)
    legacy = [] if (rid or ARGS.run_id) else await _legacy_changes()
    for c in changes:
        flt, upd = G.restore_update(c)
        flt.pop("updated_at", None)   # bandingkan isi kebijakan, bukan cap waktu
        cur = await db.warehouses.find_one({"id": c["doc_id"]}, {"_id": 0}) or {}
        after = {**c["before"], "updated_at": now_iso()}
        upd.setdefault("$set", {})["updated_at"] = after["updated_at"]
        if not ARGS.apply:
            P.change("gedung_bersama_undo", "warehouses", c["doc_id"], label=c.get("label", ""),
                     before={f: cur.get(f) for f in FIELDS}, after=after)
            continue
        res = await db.warehouses.update_one(flt, upd)
        if res.modified_count:
            P.change("gedung_bersama_undo", "warehouses", c["doc_id"], label=c.get("label", ""),
                     before={f: cur.get(f) for f in FIELDS}, after=after)
        else:
            print(f"  LEWAT {c.get('label') or c['doc_id']}: gedung sudah diubah sesudah skrip — tidak dikembalikan.")
    for c in legacy:   # format lama
        cur = await db.warehouses.find_one({"id": c["warehouse_id"]}, {"_id": 0}) or {}
        after = {**c["before"], "updated_at": now_iso()}
        if not ARGS.apply:
            P.change("gedung_bersama_undo", "warehouses", c["warehouse_id"], label=c.get("code", ""),
                     before={f: cur.get(f) for f in FIELDS}, after=after, note="jejak format lama")
            continue
        res = await db.warehouses.update_one({"id": c["warehouse_id"], "sharing_mode": "shared"}, {"$set": after})
        if res.modified_count:
            P.change("gedung_bersama_undo", "warehouses", c["warehouse_id"], label=c.get("code", ""),
                     before={f: cur.get(f) for f in FIELDS}, after=after, note="jejak format lama")
        else:
            print(f"  LEWAT {c.get('code')}: gedung sudah diubah sesudah skrip — tidak dikembalikan.")
    if ARGS.apply and legacy:
        await db.migrations.update_one({"id": FLAG}, {"$set": {"undone_at": now_iso()}, "$unset": {"runs": ""}})
    return rid


async def main() -> None:
    G.banner(ARGS)
    P = G.Plan(ARGS)
    undone = ""
    if ARGS.undo:
        undone = await apply_undo(P)
    else:
        await apply_forward(P)
    P.print()
    P.write_report()
    if ARGS.apply and P.changes:
        await P.save(db, ACTOR, kind="undo" if ARGS.undo else "apply", undone_run=undone)
    print(f"Selesai: {len(P.changes)} gedung {'diproses' if ARGS.apply else 'akan diproses (dry-run)'}.")
    await G.drain_tasks()


if __name__ == "__main__":
    asyncio.run(main())
