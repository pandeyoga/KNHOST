#!/usr/bin/env python3
"""Pembersihan data uji (fase 4 · R9) — SO MATI yang masih membawa penanda basi.

Sebelum perbaikan R8, batal/kedaluwarsa tidak menyentuh `pending_approvals` dan `has_backorder`: entri persetujuan
tetap `pending` selamanya (muncul di Pusat Persetujuan, bisa "disetujui"), SO batal tetap berlabel Backorder, dan
override kredit/harga khusus yang masih menunggu bisa kelak TERPAKAI pesanan lain. Kini setiap transisi ke status
mati memanggil `so_approvals.dead_order_patch` + `so_approvals.close_detail_docs` (lihat
`sales_order_helpers.so_transition` & `inventory_service.expire_old_reservations`). Skrip ini menjalankan helper
YANG SAMA untuk SO yang sudah mati sebelum perbaikan itu — tidak ada logika tiruan:

  * entri `pending_approvals` yang masih `pending` → `cancelled` (+ `previous_status`, alasan, pelaku, waktu);
    keputusan lama (approved/rejected/superseded) TIDAK disentuh; `approval_required`/peran dihitung ulang;
  * `has_backorder` → False (`backorders` tetap sebagai riwayat, sama dengan alur batal);
  * `price_approvals` / `credit_overrides` yang masih `pending` milik entri yang ditutup → `cancelled`;
  * `stage`/`sub_status` diselaraskan ulang (`so_status.stage_fields`, seperti `so_transition`).
Alasan mengikuti alur: SO batal → "Pesanan dibatalkan: ‹alasan batal tersimpan›"; SO kedaluwarsa → "Reservasi
pesanan kedaluwarsa". Pelaku "Sistem (pembersihan data uji)". Satu baris audit `sales_order_corrected` per SO.

Izin pemilik (26 Okt): HANYA DB uji `kn_test_trial` (DB lain ditolak skrip). Dry-run bawaan, `--apply` menulis
(tulisan berprasyarat status yang dibaca), sebelum/sesudah dicatat di `migrations`
(`id = fix_data_2026_10_26_so_mati`). Idempoten: SO yang sudah bersih tidak terpilih lagi.

Pakai (di dalam kontainer backend, repo = /app):
    python /app/scripts/fix_data_2026_10_26_so_mati.py --db kn_test_trial            # dry-run (bawaan)
    python /app/scripts/fix_data_2026_10_26_so_mati.py --db kn_test_trial --apply
"""
import argparse
import asyncio
import copy
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
    print(f"DITOLAK: izin pemilik hanya untuk DB {ALLOWED_DB}; --db {ARGS.db} tidak diproses.")
    sys.exit(2)
os.environ["DB_NAME"] = ARGS.db          # db.py membaca DB_NAME saat di-import
BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402
from dependencies import audit  # noqa: E402
from services import so_approvals  # noqa: E402
from services.so_status import stage_fields  # noqa: E402

FLAG = "fix_data_2026_10_26_so_mati"
ACTOR = "Sistem (pembersihan data uji)"
_SNAP = ("status", "has_backorder", "stage", "sub_status", "approval_required", "required_approval_role")


def _query(dead: list) -> dict:
    return {"status": {"$in": dead}, "$or": [{"pending_approvals.status": "pending"}, {"has_backorder": True}]}


def _reason(order: dict) -> str:
    """Alasan PERSIS seperti alur baru: `so_transition` (batal) / `expire_old_reservations` (kedaluwarsa)."""
    if order.get("status") == "cancelled":
        why = str(order.get("cancel_reason") or "").strip()
        return f"Pesanan dibatalkan: {why}" if why else ""
    return ""          # dead_order_patch memakai alasan baku status itu ("Reservasi pesanan kedaluwarsa", …)


def _snap(o: dict) -> dict:
    out = {k: copy.deepcopy(o.get(k)) for k in _SNAP}
    out.update({"id": o["id"], "number": o.get("number"), "entity_id": o.get("entity_id"),
                "pending_approvals": copy.deepcopy(o.get("pending_approvals") or [])})
    return out


async def _detail_docs(entries: list) -> dict:
    ids = [e.get("ref_id") for e in entries if e.get("ref_id")]
    out = {}
    for coll in ("price_approvals", "credit_overrides"):
        out[coll] = await db[coll].find({"id": {"$in": ids}}, {"_id": 0}).to_list(None) if ids else []
    return out


async def _orphan_details(dead_ids: list, covered: set) -> list:
    """Rincian pending tertaut SO mati yang TIDAK dirujuk entri pending SO-nya (di luar helper → hanya dilaporkan)."""
    out = []
    for coll, fld in (("credit_overrides", "order_id"), ("price_approvals", "so_id")):
        async for d in db[coll].find({"status": "pending", fld: {"$in": dead_ids}}, {"_id": 0, "id": 1, fld: 1}):
            if d["id"] not in covered:
                out.append(f"{coll}:{d['id']} (SO {d.get(fld)})")
    return out


async def main() -> int:
    mode = "APPLY" if ARGS.apply else "DRY-RUN"
    print(f"== {FLAG} · DB {ARGS.db} · {mode}")
    dead = list(so_approvals.dead_statuses())
    orders = await db.sales_orders.find(_query(dead), {"_id": 0}).sort("number", 1).to_list(None)
    n_pa = sum(1 for o in orders if any(p.get("status") == "pending" for p in o.get("pending_approvals") or []))
    n_bo = sum(1 for o in orders if o.get("has_backorder"))
    print(f"SO mati (status {', '.join(dead)}) dengan penanda basi: {len(orders)} · ber-entri pending {n_pa} · "
          f"has_backorder {n_bo}")
    plan, skipped, covered = [], [], set()
    for o in orders:
        st = o.get("status")
        patch, closed = so_approvals.dead_order_patch(o, st, _reason(o), ACTOR)
        if not patch:
            skipped.append({"number": o.get("number"), "status": st,
                            "reason": f"status {st} bukan transisi mati yang ditutup helper R8 (dead_order_patch)"})
            print(f"  - {o.get('number')} ({st}) → LEWATI: helper R8 tidak menutup status ini")
            continue
        patch["updated_at"] = now_iso()
        patch.update(stage_fields({**o, **patch}))
        details = await _detail_docs(closed)
        covered |= {d["id"] for docs in details.values() for d in docs if d.get("status") == "pending"}
        plan.append({"order": o, "patch": patch, "closed": closed, "details": details})
        print(f"  - {o.get('number')} [{o.get('entity_id')}] {st} · has_backorder {o.get('has_backorder')} → "
              f"{patch.get('has_backorder')} · stage {o.get('stage')} → {patch.get('stage')} · sub {o.get('sub_status')}"
              f" → {patch.get('sub_status')}")
        for e in closed:
            print(f"      entri {e.get('type')} {e.get('id')} pending → cancelled · alasan \"{e.get('cancel_reason')}\""
                  + (f" · rincian {e.get('ref_id')}" if e.get("ref_id") else ""))
        if closed:
            print(f"      approval_required {o.get('approval_required')} → {patch.get('approval_required')} · peran "
                  f"{o.get('required_approval_role')} → {patch.get('required_approval_role')}")
        for coll, docs in details.items():
            for d in docs:
                print(f"      {coll} {d['id']} status {d.get('status')}"
                      + (" → cancelled" if d.get("status") == "pending" else " (sudah diputus — tidak diubah)"))
    dead_ids = [d["id"] async for d in db.sales_orders.find({"status": {"$in": dead}}, {"_id": 0, "id": 1})]
    orphans = await _orphan_details(dead_ids, covered)
    if orphans:
        print(f"  Catatan: rincian pending tertaut SO mati TANPA entri pending (tidak disentuh): {orphans}")
    print(f"Rencana: {len(plan)} SO dirapikan · {sum(len(p['closed']) for p in plan)} entri ditutup · "
          f"{len(covered)} rincian pending dibatalkan · dilewati {len(skipped)}")
    if not ARGS.apply:
        print("DRY-RUN — tidak ada yang ditulis. Ulangi dengan --apply untuk menerapkan.")
        return 0
    if not plan:
        print("Tidak ada yang perlu dirapikan.")
        return 0
    runs, conflicts = [], []
    for p in plan:
        o, patch, closed = p["order"], p["patch"], p["closed"]
        r = await db.sales_orders.update_one({"id": o["id"], "status": o["status"]}, {"$set": patch})
        if not r.matched_count:
            conflicts.append(o.get("number"))
            print(f"  ✗ {o.get('number')}: status berubah sebelum ditulis — dilewati")
            continue
        if closed:
            await so_approvals.close_detail_docs(db, closed, closed[0].get("cancel_reason", ""), ACTOR)
        cur = await db.sales_orders.find_one({"id": o["id"]}, {"_id": 0})
        det_after = await _detail_docs(closed)
        await audit(ACTOR, "sales_order_corrected", "sales_order", o["id"],
                    {"has_backorder": cur.get("has_backorder"), "stage": cur.get("stage"),
                     "sub_status": cur.get("sub_status"), "approval_required": cur.get("approval_required"),
                     "closed_approvals": [{"id": e["id"], "type": e.get("type")} for e in closed]},
                    reason="Pembersihan data uji: penanda basi SO yang sudah "
                           + ("dibatalkan" if o["status"] == "cancelled" else "kedaluwarsa" if o["status"] == "expired"
                              else o["status"]) + " ditutup seperti alur batal/kedaluwarsa baru",
                    scope_entity_id=o.get("entity_id") or "",
                    before={"has_backorder": o.get("has_backorder"), "stage": o.get("stage"),
                            "sub_status": o.get("sub_status"), "approval_required": o.get("approval_required")},
                    source=FLAG)
        old_dec = [x for x in o.get("pending_approvals") or [] if x.get("status") != "pending"]
        new_dec = [x for x in cur.get("pending_approvals") or [] if x.get("id") in {d.get("id") for d in old_dec}]
        untouched = old_dec == new_dec
        runs.append({"before": _snap(o), "after": _snap(cur), "details_before": p["details"],
                     "details_after": det_after, "decisions_untouched": untouched})
        print(f"  ✓ {cur.get('number')}: has_backorder {cur.get('has_backorder')} · entri pending "
              f"{sum(1 for x in cur.get('pending_approvals') or [] if x.get('status') == 'pending')} · keputusan lama "
              f"utuh={untouched}")
    left = await db.sales_orders.count_documents(_query(dead))
    still = await _orphan_details(dead_ids, set())
    await db.migrations.update_one({"id": FLAG}, {
        "$set": {"applied_at": now_iso()},
        "$push": {"runs": {"at": now_iso(), "db": ARGS.db, "actor": ACTOR, "orders": runs,
                           "skipped": skipped, "conflicts": conflicts}}},
        upsert=True)
    bad = [r["after"]["number"] for r in runs if not r["decisions_untouched"]]
    print(f"Verifikasi: SO mati berpenanda basi tersisa {left} · rincian pending tertaut SO mati {len(still)} "
          f"{still or ''} · keputusan lama berubah {bad or 0} · konflik {conflicts or 0}")
    await asyncio.sleep(0.5)   # biarkan efek samping audit (cek giliran) selesai sebelum loop ditutup
    return 1 if left or still or bad or conflicts else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
