#!/usr/bin/env python3
"""Perbaikan data lama G4-12 (fase 4 · R7) — PR yang masih menunjuk PO BATAL/DITOLAK.

Sebelum perbaikan G4-12, pembatalan/penolakan PO tidak menyentuh PR asalnya: baris PR tetap
"terealisasi" ke PO mati, PR tetap `converted` ("Jadi PO") dengan `po_id`/`po_number` PO mati,
sehingga sisa kebutuhan tidak bisa direalisasikan lagi. Kini router PO memanggil
`pr_sourcing_service.release_po_realizations`; skrip ini menjalankan pasangannya untuk data lama:
`pr_sourcing_service.reconcile_dead_po_realizations()` (SATU jalur yang sama — tidak ada logika
tiruan saat menulis).

Yang berubah per PR (oleh fungsi layanan, bukan skrip):
  * realisasi baris ke PO mati ditandai `voided` (TIDAK dihapus — jejak tetap ada) & `realized_qty`
    dikurangi;
  * PR `converted` yang tidak lagi penuh → `approved` (bisa direalisasikan lagi);
  * `po_id`/`po_number` menunjuk PO hidup terakhir atau dikosongkan; `po_ids` tanpa PO mati;
  * riwayat PR mendapat entri `po_released` ("<PO> dibatalkan — …", alasan "PO sudah tidak berlaku
    (rekonsiliasi)").
Tidak ada dokumen yang dihapus. Idempoten: realisasi yang sudah `voided` dilewati.

Pakai (di dalam kontainer backend, repo = /app):
    python /app/scripts/fix_data_2026_10_26_pr_po_batal.py --db kn_test_trial            # dry-run (bawaan)
    python /app/scripts/fix_data_2026_10_26_pr_po_batal.py --db kn_test_trial --apply
"""
import argparse
import asyncio
import copy
import os
import sys
from pathlib import Path


def _args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True, help="nama DB yang diperbaiki (mis. kn_test_trial, kn_uat_23okt)")
    ap.add_argument("--apply", action="store_true", help="terapkan (tanpa ini = dry-run)")
    return ap.parse_args()


ARGS = _args()
os.environ["DB_NAME"] = ARGS.db          # db.py membaca DB_NAME saat di-import
BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402
from services import pr_sourcing_service as prs  # noqa: E402

FLAG = "fix_data_2026_10_26_pr_po_batal"


async def _dead_pos() -> dict:
    return {p["id"]: p async for p in db.purchase_orders.find(
        {"status": {"$in": list(prs.PO_DEAD_STATUSES)}}, {"_id": 0, "id": 1, "po_number": 1, "status": 1})}


async def _affected(dead: dict) -> list:
    """PR yang akan disentuh — filter SAMA dengan `reconcile_dead_po_realizations`."""
    if not dead:
        return []
    flt = {"$or": [{"items.realizations": {"$elemMatch": {
        "type": "purchase_order", "ref_id": {"$in": list(dead)}, "voided": {"$ne": True}}}},
        {"po_id": {"$in": list(dead)}}]}
    return await db.purchase_requisitions.find(flt, {"_id": 0}).sort("number", 1).to_list(None)


def _snapshot(pr: dict) -> dict:
    return {"id": pr["id"], "number": pr.get("number"), "status": pr.get("status"),
            "realization_status": pr.get("realization_status"), "po_id": pr.get("po_id") or "",
            "po_number": pr.get("po_number") or "", "po_ids": pr.get("po_ids") or [],
            "lines": [{"line_no": it.get("line_no"), "quantity": it.get("quantity"),
                       "realized_qty": it.get("realized_qty")} for it in pr.get("items") or []]}


def _simulate(pr: dict, dead: dict) -> dict:
    """Pratinjau hasil `release_po_realizations` untuk setiap PO mati yang ditunjuk PR (tanpa DB)."""
    sim = copy.deepcopy(pr)
    prs.ensure_line_shape(sim)
    targets = sorted({r["ref_id"] for it in sim["items"] for r in it.get("realizations") or []
                      if r.get("type") == "purchase_order" and r.get("ref_id") in dead and not r.get("voided")}
                     | ({sim["po_id"]} if sim.get("po_id") in dead else set()))
    notes = []
    for pid in targets:
        lines, qty, number = prs._void_po_realizations(sim, pid, actor="(dry-run)", reason="")
        number = number or dead[pid].get("po_number") or "PO"
        notes.append(f"{number} ({dead[pid]['status']}): {lines} baris dilepas, qty {qty:g}")
        if sim.get("status") == "converted" and prs.compute_realization(sim)["realization_status"] != "realized":
            sim["status"] = "approved"
        if sim.get("po_id") == pid:
            alive = [r for it in sim["items"] for r in it.get("realizations") or []
                     if r.get("type") == "purchase_order" and not r.get("voided")]
            sim["po_id"] = alive[-1]["ref_id"] if alive else ""
            sim["po_number"] = alive[-1].get("ref_number", "") if alive else ""
    summ = prs.compute_realization(sim)
    if summ["realization_status"] == "realized":
        sim["status"] = "converted"
    sim["realization_status"] = summ["realization_status"]
    sim["po_ids"] = sorted({r["ref_id"] for it in sim["items"] for r in it.get("realizations") or []
                            if r.get("type") == "purchase_order" and not r.get("voided")})
    return {"notes": notes, "after": _snapshot(sim)}


def _fmt(s: dict) -> str:
    lines = ", ".join(f"L{x['line_no']} {x['realized_qty']}/{x['quantity']}" for x in s["lines"])
    return (f"status={s['status']} realisasi={s['realization_status']} po_number={s['po_number'] or '—'} "
            f"po_ids={len(s['po_ids'])} [{lines}]")


async def main() -> int:
    mode = "APPLY" if ARGS.apply else "DRY-RUN"
    print(f"== {FLAG} · DB {ARGS.db} · {mode}")
    dead = await _dead_pos()
    print(f"PO batal/ditolak: {len(dead)}")
    prs_before = await _affected(dead)
    print(f"PR yang masih menunjuk PO mati: {len(prs_before)}")
    plan = []
    for pr in prs_before:
        before = _snapshot(pr)
        sim = _simulate(pr, dead)
        plan.append({"before": before, "after_expected": sim["after"]})
        print(f"  - {before['number']} ({pr.get('entity_id')}, sumber {pr.get('source') or '-'})")
        for n in sim["notes"]:
            print(f"      {n}")
        print(f"      sebelum : {_fmt(before)}")
        print(f"      sesudah : {_fmt(sim['after'])}")
    if not ARGS.apply:
        print("DRY-RUN — tidak ada yang ditulis. Ulangi dengan --apply untuk menerapkan.")
        return 0
    if not prs_before:
        print("Tidak ada yang perlu diperbaiki.")
        return 0
    changed = await prs.reconcile_dead_po_realizations()
    print(f"Diterapkan lewat reconcile_dead_po_realizations: {len(changed)} pembaruan PR → {sorted(set(changed))}")
    # Verifikasi: tidak ada lagi PR yang menunjuk PO mati; hasil = pratinjau.
    left = await _affected(await _dead_pos())
    mismatch = []
    for p in plan:
        cur = await db.purchase_requisitions.find_one({"id": p["before"]["id"]}, {"_id": 0})
        now = _snapshot(cur)
        exp = p["after_expected"]
        if (now["status"], now["po_number"], now["po_ids"], [x["realized_qty"] for x in now["lines"]]) != \
                (exp["status"], exp["po_number"], exp["po_ids"], [x["realized_qty"] for x in exp["lines"]]):
            mismatch.append(now["number"])
        p["after"] = now
        print(f"  ✓ {now['number']}: {_fmt(now)}")
    await db.migrations.update_one({"id": FLAG}, {
        "$set": {"applied_at": now_iso()},
        "$push": {"runs": {"at": now_iso(), "db": ARGS.db, "prs": [
            {"number": p["before"]["number"], "before": p["before"], "after": p["after"]} for p in plan]}}},
        upsert=True)
    print(f"Verifikasi: sisa PR menunjuk PO mati = {len(left)} · beda dari pratinjau = {mismatch or 0}")
    return 1 if left or mismatch else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
