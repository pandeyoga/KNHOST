#!/usr/bin/env python3
"""FIX-9 (B3a SSOT-4) — kunci cadangan makloon AKTIF yang sudah ada ke roll nyata. DB uji ATAU produksi.

Sejak FIX-9, cadangan bahan makloon dikunci per roll saat lahir (PR disetujui / MKO dibuat). Cadangan yang lahir
SEBELUM kode ini (data acuan: 300 kg Kanda `MKO-00005`, 75 kg KSC `KSC/MKO-00082`; produksi: isi `material_reservations`
apa adanya) masih berupa angka produk × PT. Skrip ini menguncinya dengan aturan yang SAMA dengan kode
(`services/makloon_roll_lock.py`): roll `available` milik PT cadangan di gudang sumber (MKO `from_warehouse_id` /
PR `warehouse_id`; kosong → gudang ber-panjang-bebas terbesar dulu), FIFO, roll utuh dulu; stok kurang → sisanya tetap
"cadangan belum terkunci" (angka stok tetap mengurangkannya, tidak ada yang hilang).

Langkah (semua idempoten; tanpa `--apply` = DRY-RUN: hanya menghitung & menampilkan rencana, tidak menulis apa pun):
  1. `orphan_locks`   — kunci makloon di roll yang cadangannya sudah tidak aktif (proses mati di tengah) → dilepas.
  2. `lock_active`    — per cadangan aktif: roll yang AKAN dikunci (nomor roll, gudang, lot, panjang) + kekurangan.
                        `--apply` mengunci lewat `makloon_roll_lock.lock` (CAS per roll; isi kekurangan saja).
  3. `mirror_resync`  — cermin `locked_qty`/`locks` cadangan yang berbeda dari roll → dibangun ulang dari roll.
Tidak menyentuh: jumlah cadangan (`qty`/`shortage_qty`), dokumen PR/MKO/SO, jurnal. Saldo segmen yang rolnya dikunci
dibangun ulang (`rebuild_balance`) — angka "Tersedia" TIDAK berubah (bagian terkunci pindah dari pengurangan agregat ke
saldo roll; `stock_figures` tidak dobel-kurang).

PAGAR DB (pola FIX-7 `data_fix_guard`; modul itu belum ada di `main` saat FIX-9 dibuat — semantik sama):
  * DB uji `kn_test_trial` / `test_database` → diterima.
  * DB produksi `kainnusantara` → WAJIB `--production` + bukti backup < 24 jam (juga untuk dry-run):
      `--backup-file <jalur>` (diperiksa: nama `kainnusantara-…archive.gz`, umur, ukuran, gzip utuh) atau
      `--backup-file kainnusantara-YYYY-MM-DD_HHMM.archive.gz` (berkas tak terlihat dari kontainer: cap waktu nama, WIB)
      atau `--backup-confirmed "<nama berkas + pemeriksa, ≥ 5 huruf>"`.
  * DB lain → DITOLAK (kode keluar 2).
JEJAK (`--apply`): per cadangan yang berubah satu baris `audit_logs` (`data_fix_applied`, sumber `<skrip>#<putaran>`)
+ baris audit `makloon_locked` dari layanan kunci; ringkasan & daftar kunci baru per putaran di `migrations`
(`id = fix_data_2026_11_10_fix9_kunci_makloon`). `--undo --apply` melepas kunci yang dibuat putaran terakhir (atau
`--run-id`) — hanya entri kunci yang masih menempel apa adanya.

Pakai (di dalam kontainer backend, repo = /app):
    python /app/scripts/fix_data_2026_11_10_fix9_kunci_makloon.py --db kn_test_trial                 # dry-run
    python /app/scripts/fix_data_2026_11_10_fix9_kunci_makloon.py --db kn_test_trial --apply
    python /app/scripts/fix_data_2026_11_10_fix9_kunci_makloon.py --db kn_test_trial --undo --apply
Produksi (sesudah `bash deploy/backup.sh`):
    docker compose exec backend python /app/scripts/fix_data_2026_11_10_fix9_kunci_makloon.py \\
        --db kainnusantara --production --backup-file kainnusantara-2026-11-10_2100.archive.gz          # dry-run
    … tambah --apply sesudah rencana dry-run diperiksa.
"""
import argparse
import asyncio
import gzip
import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

FLAG = "fix_data_2026_11_10_fix9_kunci_makloon"
TEST_DBS = ("kn_test_trial", "test_database")
PRODUCTION_DBS = ("kainnusantara",)
BACKUP_MAX_AGE_HOURS = 24
BACKUP_MIN_BYTES = 100 * 1024
ARCHIVE_MAGIC = bytes.fromhex("6de29981")
WIB = timezone(timedelta(hours=7))
ACTOR = "Sistem (FIX-9 kunci cadangan makloon per roll)"


class Refused(Exception):
    pass


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True, help=f"DB uji {list(TEST_DBS)} atau produksi {list(PRODUCTION_DBS)}")
    ap.add_argument("--apply", action="store_true", help="terapkan (tanpa ini = dry-run, tidak menulis apa pun)")
    ap.add_argument("--undo", action="store_true", help="lepas kunci putaran --apply terakhir (atau --run-id)")
    ap.add_argument("--run-id", default="", help="putaran yang dibalik (bawaan: terakhir yang belum dibalik)")
    ap.add_argument("--production", action="store_true", help="WAJIB untuk DB produksi")
    ap.add_argument("--backup-file", default="", help="jalur atau nama `<db>-YYYY-MM-DD_HHMM.archive.gz`")
    ap.add_argument("--backup-confirmed", default="", help="konfirmasi manual backup < 24 jam (≥ 5 huruf)")
    ap.add_argument("--only", default="", help="batasi ke id cadangan tertentu (pisah koma) — uji / perbaikan satu cadangan")
    ap.add_argument("--show", type=int, default=50, help="baris contoh per langkah (0 = semua)")
    ap.add_argument("--report", default="", help="tulis laporan lengkap (JSON) ke jalur ini")
    return ap


def _letters(text: str) -> int:
    return sum(1 for ch in str(text or "") if ch.isalpha())


def backup_evidence(db_name: str, backup_file: str, confirmed: str, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    if backup_file:
        path = Path(backup_file)
        if path.is_file():
            if not path.name.startswith(f"{db_name}-") or not path.name.endswith(".archive.gz"):
                raise Refused(f"berkas backup {path.name} bukan backup DB {db_name}.")
            st = path.stat()
            age_h = (now.timestamp() - st.st_mtime) / 3600
            if age_h > BACKUP_MAX_AGE_HOURS or age_h < -1:
                raise Refused(f"backup {path.name} berumur {age_h:.1f} jam — jalankan `bash deploy/backup.sh` dulu.")
            if st.st_size < BACKUP_MIN_BYTES:
                raise Refused(f"backup {path.name} hanya {st.st_size} bita — kemungkinan gagal/terpotong.")
            try:
                with gzip.open(path, "rb") as gz:
                    head = gz.read(4)
                    while gz.read(4 * 1024 * 1024):
                        pass
            except (OSError, EOFError) as exc:
                raise Refused(f"backup {path.name} rusak/terpotong: {exc}") from exc
            if head != ARCHIVE_MAGIC:
                raise Refused(f"backup {path.name} bukan arsip mongodump.")
            return {"kind": "file_verified", "name": path.name, "bytes": st.st_size, "age_hours": round(age_h, 2)}
        m = re.match(r"^(?P<db>[A-Za-z0-9_]+)-(?P<d>\d{4}-\d{2}-\d{2})_(?P<t>\d{4})\.archive\.gz$", path.name)
        if not m or m.group("db") != db_name:
            raise Refused(f"nama backup `{backup_file}` tidak berpola `{db_name}-YYYY-MM-DD_HHMM.archive.gz`.")
        stamp = datetime.strptime(f"{m.group('d')} {m.group('t')}", "%Y-%m-%d %H%M").replace(tzinfo=WIB)
        age_h = (now - stamp).total_seconds() / 3600
        if age_h > BACKUP_MAX_AGE_HOURS or age_h < -1:
            raise Refused(f"backup `{backup_file}` berumur ±{age_h:.1f} jam — jalankan `bash deploy/backup.sh` dulu.")
        return {"kind": "name_stamp", "name": path.name, "age_hours": round(age_h, 2)}
    if confirmed:
        if _letters(confirmed) < 5:
            raise Refused("--backup-confirmed wajib keterangan ≥ 5 huruf (nama berkas backup + pemeriksa).")
        return {"kind": "operator_confirmed", "note": confirmed.strip()[:300]}
    raise Refused("DB produksi wajib bukti backup < 24 jam: --backup-file atau --backup-confirmed.")


def guard(args) -> dict:
    if args.db in TEST_DBS:
        return {"production": False}
    if args.db in PRODUCTION_DBS:
        if not args.production:
            raise Refused(f"DB {args.db} = PRODUKSI — wajib --production (+ bukti backup).")
        return {"production": True, "backup": backup_evidence(args.db, args.backup_file, args.backup_confirmed)}
    raise Refused(f"DB {args.db} tidak dikenal — hanya uji {list(TEST_DBS)} atau produksi {list(PRODUCTION_DBS)}.")


ARGS = build_parser().parse_args() if __name__ == "__main__" else None
if ARGS is not None:
    try:
        GUARD = guard(ARGS)
    except Refused as exc:
        print(f"DITOLAK: {exc}")
        sys.exit(2)
    os.environ["DB_NAME"] = ARGS.db           # db.py membaca DB_NAME saat di-import
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

    from core_utils import new_id, now_iso  # noqa: E402
    from db import db  # noqa: E402
    from services import makloon_roll_lock as L  # noqa: E402


def _cut(rows: list, n: int) -> list:
    return rows if not n else rows[:n]


def _only() -> list:
    return [x.strip() for x in (ARGS.only or "").split(",") if x.strip()]


async def _audit(run_id: str, res: dict, before: dict, after: dict, action: str = "data_fix_applied") -> None:
    await db.audit_logs.insert_one({
        "id": new_id("audit"), "actor": ACTOR, "actor_id": "", "role": "system/data_fix", "action": action,
        "source": f"{FLAG}#{run_id}", "entity_type": "material_reservations", "entity_id": res["id"],
        "scope_entity_id": res.get("owner_entity_id") or None, "before": before, "after": after,
        "reason": "FIX-9 kunci cadangan makloon per roll", "timestamp": now_iso(), "created_at": now_iso()})


async def step_orphans(apply: bool) -> dict:
    rows = await L.orphan_locks(fix=apply, actor=ACTOR, only=_only() or None)
    return {"count": len(rows), "qty": round(sum(r["qty"] for r in rows), 2), "rows": rows}


async def step_lock_active(apply: bool, run_id: str) -> dict:
    out, new_locks = [], []
    whs = {w["id"]: w.get("code") or w.get("name") or w["id"]
           async for w in db.warehouses.find({}, {"_id": 0, "id": 1, "code": 1, "name": 1})}
    q = {"status": "active", **({"id": {"$in": _only()}} if _only() else {})}
    async for res in db.material_reservations.find(q, {"_id": 0, "history": 0}).sort("created_at", 1):
        have = round(sum(x["qty"] for x in await L.actual_locks(res["id"])), 2)
        need = round(float(res.get("qty") or 0) - have, 2)
        src = await L.source_warehouse(res, save=False)   # cadangan lama: dari MKO/PR (disimpan saat --apply)
        row = {"reservation_id": res["id"], "doc": L.doc_number(res), "product_id": res.get("product_id"),
               "entity_id": res.get("owner_entity_id"), "qty": float(res.get("qty") or 0), "locked_before": have,
               "source_warehouse": whs.get(src, src) if src else "(gudang bebas terbesar)", "rolls": []}
        if need > L.LOCK_EPS:
            if apply:
                before = {"locked_qty": res.get("locked_qty") or 0.0}
                got = await L.lock(res["id"], ACTOR, "migrasi FIX-9 — cadangan lama dikunci ke roll")
                row["rolls"] = [{"roll_no": x["roll_no"], "warehouse": whs.get(x["warehouse_id"], x["warehouse_id"]),
                                 "qty": x["qty"]} for x in got["rolls"]]
                row["locked_after"] = got["locked_qty"]
                row["shortage"] = got["unlocked_qty"]
                new_locks += [{"reservation_id": res["id"], "roll_id": x["roll_id"], "rsv_id": x["rsv_id"],
                               "qty": x["qty"]} for x in got["rolls"]]
                if got["newly_locked"] > 0:
                    await _audit(run_id, res, before, {"locked_qty": got["locked_qty"],
                                                       "rolls": row["rolls"][:30]})
            else:
                steps = L.plan(await L.candidates(res, [src] if src else None), need, src)
                row["rolls"] = [{"roll_no": r.get("roll_no") or r["id"], "warehouse": whs.get(r["warehouse_id"],
                                                                                           r["warehouse_id"]),
                                 "lot": r.get("lot") or "", "qty": q} for r, q in steps]
                planned = round(sum(q for _r, q in steps), 2)
                row["locked_after"] = round(have + planned, 2)
                row["shortage"] = round(max(float(res.get("qty") or 0) - have - planned, 0.0), 3)
        else:
            row["locked_after"] = have
            row["shortage"] = round(max(float(res.get("qty") or 0) - have, 0.0), 3)
        out.append(row)
    return {"count": len(out), "to_lock": sum(1 for r in out if r["rolls"]),
            "qty_locked_new": round(sum(sum(x["qty"] for x in r["rolls"]) for r in out), 2),
            "shortage": round(sum(r["shortage"] for r in out), 3), "rows": out, "_new_locks": new_locks}


async def step_mirror(apply: bool) -> dict:
    rows = []
    q = {"$or": [{"status": "active"}, {"locked_qty": {"$gt": 0}}], **({"id": {"$in": _only()}} if _only() else {})}
    async for res in db.material_reservations.find(q, {"_id": 0, "id": 1, "locked_qty": 1, "status": 1}):
        actual = round(sum(x["qty"] for x in await L.actual_locks(res["id"])), 3)
        if abs(actual - float(res.get("locked_qty") or 0)) > L.LOCK_EPS:
            rows.append({"reservation_id": res["id"], "mirror": res.get("locked_qty"), "actual": actual})
            if apply:
                await L.sync(res["id"])
    return {"count": len(rows), "rows": rows}


async def undo(run_id: str) -> dict:
    mig = await db.migrations.find_one({"id": FLAG}, {"_id": 0}) or {}
    runs = [r for r in mig.get("runs") or [] if r.get("mode") == "apply" and not r.get("undone_at")
            and (r.get("new_locks") or run_id)]
    run = next((r for r in runs if r["run_id"] == run_id), None) if run_id else (runs[-1] if runs else None)
    if not run:
        return {"count": 0, "note": "tidak ada putaran --apply yang belum dibalik"}
    freed = []
    for lk in run.get("new_locks") or []:
        roll = await db.inventory_rolls.find_one({"id": lk["roll_id"], "length_reservations.id": lk["rsv_id"]},
                                                 {"_id": 0, "id": 1, "roll_no": 1})
        if not roll:
            continue
        if ARGS.apply:
            await db.inventory_rolls.update_one(
                {"id": lk["roll_id"], "length_reservations.id": lk["rsv_id"]},
                [{"$set": {"length_reservations": {"$filter": {"input": "$length_reservations", "as": "r",
                                                               "cond": {"$ne": ["$$r.id", lk["rsv_id"]]}}}}},
                 {"$set": {"length_reserved": {"$round": [{"$sum": "$length_reservations.qty"}, 2]},
                           "updated_at": now_iso()}}])
        freed.append({**lk, "roll_no": roll.get("roll_no")})
    if ARGS.apply:
        from services.roll_service import rebuild_balance
        segs = set()
        async for r in db.inventory_rolls.find({"id": {"$in": [x["roll_id"] for x in freed]}},
                                               {"_id": 0, "product_id": 1, "warehouse_id": 1, "owner_entity_id": 1}):
            segs.add((r["product_id"], r["warehouse_id"], r["owner_entity_id"]))
        for p, w, o in segs:
            await rebuild_balance(p, w, o)
        for rid in {x["reservation_id"] for x in freed}:
            res = await db.material_reservations.find_one({"id": rid}, {"_id": 0, "id": 1, "owner_entity_id": 1})
            before = await L.actual_locks(rid)
            await L.sync(rid)
            if res:
                await _audit(run["run_id"], res, {"note": "kunci putaran dibalik"},
                             {"locked_qty": round(sum(x["qty"] for x in await L.actual_locks(rid)), 3),
                              "had_locks": len(before)}, action="data_fix_undone")
        await db.migrations.update_one({"id": FLAG, "runs.run_id": run["run_id"]},
                                       {"$set": {"runs.$.undone_at": now_iso()}})
    return {"count": len(freed), "run_id": run["run_id"], "rows": freed}


async def main() -> int:
    apply, run_id = ARGS.apply, uuid.uuid4().hex[:10]
    mode = ("UNDO " if ARGS.undo else "") + ("DITERAPKAN" if apply else "DRY-RUN (tidak ada yang diubah)")
    print(f"{mode} — DB {ARGS.db}" + (" · PRODUKSI" if GUARD.get("production") else "")
          + (f" · backup {GUARD['backup']}" if GUARD.get("backup") else ""))
    if ARGS.undo:
        out = {"undo": await undo(ARGS.run_id)}
    else:
        out = {"orphan_locks": await step_orphans(apply),
               "lock_active": await step_lock_active(apply, run_id),
               "mirror_resync": await step_mirror(apply)}
    new_locks = out.get("lock_active", {}).pop("_new_locks", [])
    for k, v in out.items():
        print(f"\n[{k}] jumlah {v.get('count', 0)}" + "".join(
            f" · {kk} {v[kk]}" for kk in ("to_lock", "qty_locked_new", "shortage", "qty") if kk in v))
        for r in _cut(v.get("rows") or [], ARGS.show):
            if k == "lock_active":
                rolls = ", ".join(f"{x['roll_no']}@{x['warehouse']} {x['qty']:g}" for x in r["rolls"][:12])
                more = f" … +{len(r['rolls']) - 12} roll" if len(r["rolls"]) > 12 else ""
                print(f"  {r['doc'] or r['reservation_id']:<22} {r['product_id']} {r['entity_id']}: cadangan "
                      f"{r['qty']:g}, terkunci {r['locked_before']:g} → {r['locked_after']:g}, kekurangan "
                      f"{r['shortage']:g} · gudang {r['source_warehouse']}" + (f"\n      roll: {rolls}{more}" if rolls else ""))
            else:
                print(f"  {r}")
    if ARGS.report:
        Path(ARGS.report).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        print(f"\nlaporan lengkap: {ARGS.report}")
    if apply and not ARGS.undo:
        summary = {k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in out.items()}
        await db.migrations.update_one({"id": FLAG}, {"$set": {"id": FLAG, "applied": True, "updated_at": now_iso()},
                                                      "$push": {"runs": {
                                                          "run_id": run_id, "mode": "apply", "db": ARGS.db,
                                                          "only": _only(),
                                                          "production": GUARD.get("production", False),
                                                          "backup": GUARD.get("backup"), "at": now_iso(), "by": ACTOR,
                                                          "summary": summary, "new_locks": new_locks}}}, upsert=True)
        print(f"\nputaran {run_id} dicatat di migrations.{FLAG}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
