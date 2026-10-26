#!/usr/bin/env python3
"""Perbaikan data lama K-04/D2 (fase 4 · R7) — segmen saldo stok BASI (proyeksi ≠ roll).

`inventory_balances` adalah PROYEKSI dari `inventory_rolls` per segmen (produk × gudang × pemilik), dibangun
oleh `roll_service.rebuild_balance`. Jalur lama/residu uji yang mengubah roll tanpa memanggil rebuild
meninggalkan segmen basi (mis. saldo tersedia 10 padahal roll 0). Skrip ini:
  1. menghitung proyeksi bucket tiap segmen dari roll dengan aturan YANG SAMA dengan `rebuild_balance`
     (status → bucket, klaim perpindahan → hold, panjang dipesan → bucket reservasi, konversi satuan dasar);
  2. membandingkannya dengan saldo tersimpan (semua bucket + on_hand) → daftar segmen basi, termasuk segmen
     ber-roll tanpa dokumen saldo dan saldo ber-isi tanpa roll;
  3. `--apply`: memanggil `roll_service.rebuild_balance` HANYA untuk segmen basi (bukan rebuild_all yang
     menghapus semua saldo), lalu menghitung ulang → sisa basi harus 0.
Tidak ada dokumen yang dihapus. Nilai turunan PO/ATP (on_order, incoming, atp) ikut disegarkan oleh rebuild.

Pakai (di dalam kontainer backend, repo = /app):
    python /app/scripts/fix_data_2026_10_26_saldo_basi.py --db kn_test_trial            # dry-run (bawaan)
    python /app/scripts/fix_data_2026_10_26_saldo_basi.py --db kn_test_trial --apply
"""
import argparse
import asyncio
import os
import sys
from collections import defaultdict
from pathlib import Path


def _args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True, help="nama DB yang diperbaiki (mis. kn_test_trial, kn_uat_23okt)")
    ap.add_argument("--apply", action="store_true", help="terapkan (tanpa ini = dry-run)")
    ap.add_argument("--tol", type=float, default=0.01, help="toleransi selisih per bucket (bawaan 0,01)")
    return ap.parse_args()


ARGS = _args()
os.environ["DB_NAME"] = ARGS.db          # db.py membaca DB_NAME saat di-import
BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402
from services import roll_service as rs  # noqa: E402

FLAG = "fix_data_2026_10_26_saldo_basi"
SEG_KEYS = ("product_id", "warehouse_id", "owner_entity_id")


async def _project(rolls: list, prod: dict) -> dict:
    """Bucket hasil `rebuild_balance` untuk satu segmen — salinan baca-saja dari loop di roll_service."""
    buckets = {b: 0.0 for b in rs.ALL_BUCKETS}
    base = (prod.get("base_unit") or "meter").lower()
    unconvertible = 0
    for r in rolls:
        status = r.get("status")
        length = float(r.get("length_remaining", 0) or 0)
        ru = (r.get("unit") or base).lower()
        if ru != base and length:
            try:
                length = await rs.to_base_qty(prod, length, ru)
            except Exception:  # noqa: BLE001 — sama dengan rebuild: roll tak terkonversi tidak dijumlahkan
                unconvertible += 1
                continue
        bucket = (rs.PHYSICAL_STATUS_TO_BUCKET.get(status) or rs.TRANSIT_STATUS_TO_BUCKET.get(status)
                  or rs.OFFSITE_OWNED_STATUS_TO_BUCKET.get(status))
        if bucket == "available_qty" and (r.get("active_movement") or {}).get("id"):
            bucket = "hold_qty"
        raw_len = float(r.get("length_remaining", 0) or 0)
        if bucket == "available_qty" and float(r.get("length_reserved") or 0) > 0 and raw_len > 0:
            ratio = length / raw_len
            for x in r.get("length_reservations") or []:
                b = rs.PHYSICAL_STATUS_TO_BUCKET.get(x.get("status") or "reserved", "reserved_qty")
                q = float(x.get("qty") or 0) * ratio
                buckets[b] += q
                length -= q
        if bucket:
            buckets[bucket] += length
    out = {b: round(v, 2) for b, v in buckets.items()}
    out["on_hand_qty"] = round(sum(buckets[b] for b in rs.PHYSICAL_STATUS_TO_BUCKET.values()), 2)
    out["_unconvertible"] = unconvertible
    return out


async def _scan() -> list:
    rolls_by = defaultdict(list)
    async for r in db.inventory_rolls.find({}, {"_id": 0, "id": 1, "status": 1, "length_remaining": 1, "unit": 1,
                                                "active_movement": 1, "length_reserved": 1,
                                                "length_reservations": 1, **{k: 1 for k in SEG_KEYS}}):
        rolls_by[tuple(r.get(k) for k in SEG_KEYS)].append(r)
    bal_by = {}
    async for b in db.inventory_balances.find({}, {"_id": 0}):
        bal_by[tuple(b.get(k) for k in SEG_KEYS)] = b
    prods = {}
    stale = []
    for seg in sorted(set(rolls_by) | set(bal_by), key=lambda s: tuple(str(x) for x in s)):
        pid = seg[0]
        if pid not in prods:
            prods[pid] = await db.products.find_one({"id": pid}, {"_id": 0, "base_unit": 1, "sku": 1, "name": 1,
                                                                  "uom_conversion": 1, "kg_per_meter": 1, "gsm": 1,
                                                                  "width_cm": 1}) or {}
        proj = await _project(rolls_by.get(seg, []), prods[pid])
        bal = bal_by.get(seg)
        diffs = {}
        for k in list(rs.ALL_BUCKETS) + ["on_hand_qty"]:
            have = round(float((bal or {}).get(k) or 0), 2)
            if abs(have - proj[k]) > ARGS.tol:
                diffs[k] = (have, proj[k])
        if bal is None and rolls_by.get(seg):
            diffs.setdefault("_dokumen_saldo", ("tidak ada", f"{len(rolls_by[seg])} roll"))
        if diffs:
            stale.append({"seg": dict(zip(SEG_KEYS, seg)), "sku": prods[pid].get("sku") or "",
                          "rolls": len(rolls_by.get(seg, [])), "has_balance": bal is not None, "diffs": diffs})
    return stale


async def _names() -> tuple:
    whs = {w["id"]: w.get("code") or w.get("name") async for w in db.warehouses.find({}, {"_id": 0, "id": 1, "code": 1, "name": 1})}
    ents = {e["id"]: e.get("doc_prefix") or e.get("name") async for e in db.business_entities.find({}, {"_id": 0, "id": 1, "doc_prefix": 1, "name": 1})}
    return whs, ents


def _line(s: dict, whs: dict, ents: dict) -> str:
    g = s["seg"]
    d = "; ".join(f"{k} {a}→{b}" for k, (a, b) in s["diffs"].items())
    return (f"{g['product_id']} ({s['sku']}) · {g['warehouse_id']} ({whs.get(g['warehouse_id'], 'gudang tak dikenal')}) · "
            f"{g['owner_entity_id']} ({ents.get(g['owner_entity_id'], '?')}) · roll {s['rolls']}: {d}")


async def main() -> int:
    mode = "APPLY" if ARGS.apply else "DRY-RUN"
    print(f"== {FLAG} · DB {ARGS.db} · {mode}")
    n_bal = await db.inventory_balances.count_documents({})
    n_roll = await db.inventory_rolls.count_documents({})
    stale = await _scan()
    whs, ents = await _names()
    print(f"Saldo {n_bal} dokumen · roll {n_roll} · segmen basi: {len(stale)}  (format: bucket tersimpan→proyeksi roll)")
    for s in stale:
        print("  - " + _line(s, whs, ents))
    if not ARGS.apply:
        print("DRY-RUN — tidak ada yang ditulis. Ulangi dengan --apply untuk menerapkan.")
        return 0
    for s in stale:
        g = s["seg"]
        await rs.rebuild_balance(g["product_id"], g["warehouse_id"], g["owner_entity_id"])
    left = await _scan()
    await db.migrations.update_one({"id": FLAG}, {
        "$set": {"applied_at": now_iso()},
        "$push": {"runs": {"at": now_iso(), "db": ARGS.db, "rebuilt": len(stale),
                           "segments": [{**s["seg"], "sku": s["sku"], "rolls": s["rolls"],
                                         "before_after": {k: list(v) for k, v in s["diffs"].items()}} for s in stale]}}},
        upsert=True)
    print(f"Rebuild {len(stale)} segmen · sisa basi sesudah rebuild: {len(left)}")
    for s in left:
        print("  ! masih basi: " + _line(s, whs, ents))
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
