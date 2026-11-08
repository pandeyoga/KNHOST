#!/usr/bin/env python3
"""PREP-C — nilai awal profil gedung sesuai fakta pemilik 8 Nov 2026 (K-GDG-01/04/05/06/07). HANYA DB uji `kn_test_trial`.

Fakta pemilik yang diisikan:
  * K-GDG-01 — gate fisik HANYA di gedung PENYIMPANAN di Rancamalang & Soreang (`has_gate` + mode `gate`); gedung lain
    (transit, Jakarta, gedung inspeksi/retur) = handheld. Pasangan/perangkat gate yang sudah tercatat dipertahankan.
  * K-GDG-04 — Gedung Retur Rancamalang (`RCM-RETUR`) = tempat inspeksi → peran `inspection` ditambahkan.
  * K-GDG-05/06 — `storage_form` kosong → `rack`, `stock_mode` kosong → `roll_tagged` (bawaan; ubah di Profil Gedung).
  * K-GDG-07 (opsional, `--with-shared`) — semua gedung dipakai bersama: `sharing_mode` dedicated → shared.
Yang TIDAK disentuh: stok, roll, struktur bin, aturan simpan. Idempoten (gedung yang sudah sesuai dilewati).
Jejak: satu dokumen `migrations` (`id = fix_data_2026_11_08_profil_gedung`) berisi sebelum/sesudah + audit per gedung.

Pakai (di dalam kontainer backend, repo = /app):
    python /app/scripts/fix_data_2026_11_08_profil_gedung.py --db kn_test_trial            # dry-run (bawaan)
    python /app/scripts/fix_data_2026_11_08_profil_gedung.py --db kn_test_trial --apply
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
    ap.add_argument("--with-shared", action="store_true", help="K-GDG-07: ubah gedung khusus PT menjadi bersama")
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
from dependencies import audit  # noqa: E402
from services import warehouse_profile_service as whp  # noqa: E402

FLAG = "fix_data_2026_11_08_profil_gedung"
ACTOR = "Sistem (nilai awal profil gedung)"
GATE_SITES = {"rancamalang", "soreang"}
INSPECTION_CODES = {"RCM-RETUR"}


def plan_for(w: dict, site_name: str) -> dict:
    roles = set(w.get("roles") or [])
    if w.get("code") in INSPECTION_CODES:
        roles |= {"inspection"}
    storage_only = bool(roles & whp.STORAGE_ROLES) and not roles & {"inspection", "return"}
    gate_on = site_name.lower() in GATE_SITES and storage_only
    cur = whp.normalize_gate_config(w.get("gate_config"))
    gate = {**cur, "has_gate": gate_on, "physical_gate": gate_on,
            "confirm_mode": "gate" if gate_on else "handheld"}
    want = {"roles": sorted(roles), "gate_config": gate,
            "stock_mode": w.get("stock_mode") or "roll_tagged", "storage_form": w.get("storage_form") or "rack"}
    if ARGS.with_shared and w.get("sharing_mode") == "dedicated":
        want.update({"sharing_mode": "shared", "entity_ids": []})
    if roles == set(w.get("roles") or []):
        want.pop("roles")   # urutan beda saja bukan perubahan
    return {k: v for k, v in want.items() if w.get(k) != v}


async def main() -> None:
    sites = {s["id"]: s.get("name", "") async for s in db.warehouse_sites.find({}, {"_id": 0, "id": 1, "name": 1})}
    rows = []
    async for w in db.warehouses.find({"active": {"$ne": False}}, {"_id": 0}).sort("code", 1):
        diff = plan_for(w, sites.get(w.get("site_id") or "", ""))
        if diff:
            rows.append((w, diff))
    print(f"{'TERAPKAN' if ARGS.apply else 'DRY-RUN'} — DB {ARGS.db}: {len(rows)} gedung perlu diubah")
    for w, diff in rows:
        g = diff.get("gate_config")
        bits = [f"peran → {', '.join(diff['roles'])}" if "roles" in diff else "",
                (f"gate → {'ADA (mode gate)' if g['has_gate'] else 'tanpa gate (handheld)'}" if g else ""),
                f"stok → {diff['stock_mode']}" if "stock_mode" in diff else "",
                f"bentuk → {diff['storage_form']}" if "storage_form" in diff else "",
                "pemakaian → bersama" if "sharing_mode" in diff else ""]
        print(f"  {w.get('code', ''):<14} {w.get('name', '')[:40]:<40} " + " · ".join(b for b in bits if b))
    if not ARGS.apply or not rows:
        return
    log = []
    for w, diff in rows:
        res = await db.warehouses.update_one({"id": w["id"], "updated_at": w.get("updated_at")},
                                             {"$set": {**diff, "updated_at": now_iso()}})
        if not res.modified_count:
            print(f"  LEWAT {w.get('code')}: gedung berubah bersamaan — jalankan ulang skrip.")
            continue
        log.append({"warehouse_id": w["id"], "code": w.get("code"), "before": {k: w.get(k) for k in diff}, "after": diff})
        await audit(ACTOR, "warehouse_profile_initialized", "warehouse", w["id"], diff, reason=FLAG)
    await db.migrations.update_one({"id": FLAG}, {"$set": {"id": FLAG, "applied_at": now_iso(), "by": ACTOR},
                                                  "$push": {"runs": {"at": now_iso(), "changes": log}}}, upsert=True)
    print(f"Selesai: {len(log)} gedung diperbarui (jejak di migrations.{FLAG}).")


if __name__ == "__main__":
    asyncio.run(main())
