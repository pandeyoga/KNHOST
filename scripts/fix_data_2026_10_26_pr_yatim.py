#!/usr/bin/env python3
"""Pembersihan data uji (fase 4 · R9) — PR yatim dari Pesanan Khusus yang sudah dihapus.

PR-00106, PR-00151, PR-00174, PR-00179 (DB uji) lahir dari Pesanan Khusus (`source = special_order`) milik uji
otomatis; Pesanan Khusus sumbernya (`source_ref_id`) sudah dihapus pembersihan uji, dan PO-nya dibatalkan ±0,5 detik
setelah lahir. Sejak perbaikan data R7 (rekonsiliasi PR ↔ PO batal) keempatnya kembali "Disetujui" dan bisa
direalisasikan lagi — padahal tidak ada pesanan yang membutuhkannya. Izin lanjutan (26 Okt): 6 PR yatim lain yang
ditemukan dry-run pertama (PR-00032/48/55/70/72/87 — "Disetujui", belum pernah terealisasi) ikut dibatalkan.

Izin pemilik (26 Okt, HANYA DB uji `kn_test_trial`): batalkan lewat ALUR BATAL PR yang ada, bukan set field mentah —
`purchase_requisition_service.cancel_requisition` (status `cancelled`, `cancel_reason`, `cancelled_by`,
`cancelled_at`, reservasi bahan PR dilepas) + baris audit `pr_cancelled` (sama dengan
`POST /purchase-requisitions/{id}/cancel`). Alasan: "Residu uji — Pesanan Khusus sumber sudah dihapus".

PR target hanya dibatalkan bila masih sesuai deskripsi izin (sumber `special_order`, Pesanan Khusus sumbernya tidak
ada, status belum terminal, TIDAK ada realisasi hidup — baris terealisasi, realisasi belum `voided`, `po_ids`/Order
Makloon, atau `po_id` ke PO yang belum batal); selain itu DILEWATI dan dicatat. PR yatim lain yang ditemukan hanya
dilaporkan (tidak disentuh — di luar izin). Dry-run bawaan, `--apply` menulis, sebelum/sesudah dicatat di `migrations`
(`id = fix_data_2026_10_26_pr_yatim`). Idempoten: PR yang sudah dibatalkan skrip ini dilewati.

Pakai (di dalam kontainer backend, repo = /app):
    python /app/scripts/fix_data_2026_10_26_pr_yatim.py --db kn_test_trial            # dry-run (bawaan)
    python /app/scripts/fix_data_2026_10_26_pr_yatim.py --db kn_test_trial --apply
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
    print(f"DITOLAK: izin pemilik hanya untuk DB {ALLOWED_DB}; --db {ARGS.db} tidak diproses.")
    sys.exit(2)
os.environ["DB_NAME"] = ARGS.db          # db.py membaca DB_NAME saat di-import
BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402
from dependencies import audit  # noqa: E402
from services import purchase_requisition_service as prsvc  # noqa: E402

FLAG = "fix_data_2026_10_26_pr_yatim"
ACTOR = "Sistem (pembersihan data uji)"
REASON = "Residu uji — Pesanan Khusus sumber sudah dihapus"
# 4 PR pertama = izin awal R9; 6 berikutnya = izin lanjutan pemilik 26 Okt ("ya setuju semua usulan") — PR yatim
# yang ditemukan dry-run pertama (kondisi sama, belum pernah terealisasi).
TARGETS = ("PR-00106", "PR-00151", "PR-00174", "PR-00179",
           "PR-00032", "PR-00048", "PR-00055", "PR-00070", "PR-00072", "PR-00087")
PO_DEAD = ("cancelled", "rejected")
_SNAP = ("id", "number", "entity_id", "status", "realization_status", "source", "source_ref_id", "po_number",
         "cancel_reason", "cancelled_by", "cancelled_at", "updated_at")


def _snap(pr: dict) -> dict:
    return {k: pr.get(k) for k in _SNAP}


async def _source_missing(pr: dict) -> bool:
    ref = pr.get("source_ref_id") or ""
    return bool(ref) and not await db.special_orders.count_documents({"id": ref})


async def _active_realization(pr: dict) -> list:
    """Realisasi yang masih HIDUP (bukan `voided`, dokumen tujuan tidak batal) — PR seperti ini tidak dibatalkan."""
    out = []
    for it in pr.get("items") or []:
        if float(it.get("realized_qty") or 0) > 0.001:
            out.append(f"baris {it.get('line_no')} terealisasi {it.get('realized_qty')}")
        for r in it.get("realizations") or []:
            if not r.get("voided"):
                out.append(f"realisasi {r.get('type')} {r.get('ref_number') or r.get('ref_id')} belum dibatalkan")
    if pr.get("po_ids") or pr.get("makloon_order_ids"):
        out.append(f"po_ids {pr.get('po_ids')} / makloon {pr.get('makloon_order_ids')}")
    if pr.get("po_id"):
        po = await db.purchase_orders.find_one({"id": pr["po_id"]}, {"_id": 0, "status": 1, "po_number": 1})
        if po and po.get("status") not in PO_DEAD:
            out.append(f"PO {po.get('po_number')} masih {po.get('status')}")
    return out


async def _reservations(pr_id: str) -> int:
    return await db.material_reservations.count_documents(
        {"$or": [{"ref_id": pr_id}, {"pr_id": pr_id}], "status": {"$nin": ["released", "consumed", "cancelled"]}})


async def main() -> int:
    mode = "APPLY" if ARGS.apply else "DRY-RUN"
    print(f"== {FLAG} · DB {ARGS.db} · {mode}")
    plan, skipped, done = [], [], []
    for num in TARGETS:
        pr = await db.purchase_requisitions.find_one({"number": num}, {"_id": 0})
        if pr and pr.get("status") == "cancelled" and pr.get("cancel_reason") == REASON:
            done.append(num)
            print(f"  - {num} → sudah dibatalkan run sebelumnya ({pr.get('cancelled_at')})")
            continue
        why = []
        if not pr:
            why.append("PR tidak ditemukan")
        else:
            if pr.get("source") != "special_order":
                why.append(f"sumber {pr.get('source')!r}, bukan special_order")
            if not await _source_missing(pr):
                why.append(f"Pesanan Khusus sumber {pr.get('source_ref_id')!r} masih ada / tidak tercatat")
            if pr.get("status") in prsvc.PR_TERMINAL:
                why.append(f"status sudah {pr.get('status')}")
            why += await _active_realization(pr)
        if why:
            skipped.append({"number": num, "reasons": why})
            print(f"  - {num} → LEWATI: {'; '.join(why)}")
            continue
        res = await _reservations(pr["id"])
        plan.append(pr)
        dangling = f" · po_id lama menunjuk PO batal {pr.get('po_number')}" if pr.get("po_id") else ""
        print(f"  - {num} [{pr.get('entity_id')}] {pr.get('status')} · realisasi {pr.get('realization_status')} · "
              f"sumber Pesanan Khusus {pr.get('source_ref_id')} (sudah dihapus) · reservasi bahan aktif {res}"
              f"{dangling} → batalkan (\"{REASON}\")")
    # PR yatim lain (di luar izin) — hanya dilaporkan.
    others = []
    async for pr in db.purchase_requisitions.find(
            {"source": "special_order", "number": {"$nin": list(TARGETS)},
             "status": {"$nin": list(prsvc.PR_TERMINAL)}}, {"_id": 0}).sort("number", 1):
        if await _source_missing(pr):
            others.append(f"{pr['number']} ({pr.get('status')}, realisasi {pr.get('realization_status')})")
    if others:
        print(f"  Catatan: PR lain dari Pesanan Khusus yang sudah dihapus — DI LUAR izin, tidak disentuh: "
              f"{', '.join(others)}")
    print(f"Rencana: batalkan {len(plan)} PR · sudah dibatalkan sebelumnya {len(done)} · dilewati {len(skipped)}")
    if not ARGS.apply:
        print("DRY-RUN — tidak ada yang ditulis. Ulangi dengan --apply untuk menerapkan.")
        return 0
    if not plan:
        print("Tidak ada yang perlu dibatalkan.")
        return 0
    runs, failed = [], []
    for pr in plan:
        try:
            doc = await prsvc.cancel_requisition(pr["id"], reason=REASON, actor_name=ACTOR)
        except ValueError as exc:
            failed.append(f"{pr['number']}: {exc}")
            print(f"  ✗ {pr['number']}: {exc}")
            continue
        await audit(ACTOR, "pr_cancelled", "purchase_requisition", pr["id"], {"reason": REASON},
                    reason=REASON, scope_entity_id=pr.get("entity_id") or "", source=FLAG)
        runs.append({"before": _snap(pr), "after": _snap(doc)})
        print(f"  ✓ {doc['number']}: status {doc.get('status')} · alasan \"{doc.get('cancel_reason')}\" · oleh "
              f"{doc.get('cancelled_by')} · reservasi aktif {await _reservations(pr['id'])}")
    left = await db.purchase_requisitions.count_documents(
        {"number": {"$in": [p["number"] for p in plan]}, "status": {"$ne": "cancelled"}})
    await db.migrations.update_one({"id": FLAG}, {
        "$set": {"applied_at": now_iso()},
        "$push": {"runs": {"at": now_iso(), "db": ARGS.db, "actor": ACTOR, "reason": REASON, "prs": runs,
                           "skipped": skipped, "failed": failed, "other_orphans_not_touched": others}}},
        upsert=True)
    print(f"Verifikasi: PR target belum batal {left} · gagal {failed or 0}")
    await asyncio.sleep(0.5)   # biarkan efek samping audit (cek giliran) selesai sebelum loop ditutup
    return 1 if left or failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
