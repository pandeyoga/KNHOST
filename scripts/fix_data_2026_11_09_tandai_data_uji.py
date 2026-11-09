#!/usr/bin/env python3
"""FIX-1 (B1 K-B1-10, UI-05; B3a §8) — TANDAI residu data uji agar tidak tampil di pilihan kerja. TANPA menghapus.
DB uji ATAU produksi (FIX-7: `--production`).

Yang ditandai `is_test: true` (+ `test_marked_at`, `test_marked_by`) — hanya pola yang JELAS uji:
  * gudang  : kode berawalan `TEST-` atau nama berawalan `TEST_` (6 gudang `TEST_WH …` di data acuan);
  * site    : nama/kode berawalan `TEST_` (3 `TEST_SITE …`);
  * PT      : nama legal berawalan `PT Uji Provisioning` (3 PT).
Akibat penanda (kode FIX-1): gudang/site/PT bertanda tidak ditawarkan di pemilih bawaan (`/warehouses`,
`/warehouse-sites`, `/entities`, pengalih PT), tidak ikut penugasan dinamis admin/manajer, dan gedung bertanda tidak
ikut tampilan "Semua lokasi" daftar tugas/stok WMS-RFID. Datanya TIDAK berubah; layar master tetap bisa melihatnya
(`include_test=true`/`scope=all`). Uji otomatis yang membuat gudang uji BARU tidak terpengaruh (penanda hanya dipasang
skrip ini, bukan dari pola nama saat jalan). Di produksi: periksa daftar dry-run — data nyata yang kebetulan bernama
`TEST…` ikut tertandai (bisa dibalik dengan `--undo`).

Pembalik: `--undo` memulihkan nilai sebelum dari jejak FIX-7 (`migrations`); penanda dari putaran lama (sebelum
FIX-7, tanpa jejak nilai sebelum) dicabut berdasar `test_marked_by`.
Jejak: per dokumen satu baris `audit_logs` + dokumen `migrations` (`id = fix_data_2026_11_09_tandai_data_uji…`).

Pakai (di dalam kontainer backend, repo = /app) — DB uji:
    python /app/scripts/fix_data_2026_11_09_tandai_data_uji.py --db kn_test_trial            # dry-run (bawaan)
    python /app/scripts/fix_data_2026_11_09_tandai_data_uji.py --db kn_test_trial --apply
    python /app/scripts/fix_data_2026_11_09_tandai_data_uji.py --db kn_test_trial --undo --apply
Produksi: tambah `--db kainnusantara --production --backup-file <kainnusantara-YYYY-MM-DD_HHMM.archive.gz>` —
panduan lengkap `docs/audit/2026-11-09-wms-rfid/hasil/PANDUAN-SKRIP-DATA-PRODUKSI.md`.
"""
import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
from services import data_fix_guard as G  # noqa: E402

FLAG = "fix_data_2026_11_09_tandai_data_uji"
ARGS = G.parse_and_guard(G.build_parser(__doc__.splitlines()[0]), FLAG)

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402

ACTOR = "Sistem (penanda data uji K-B1-10)"
RULES = {
    "warehouses": {"$or": [{"code": {"$regex": r"^TEST-", "$options": "i"}}, {"name": {"$regex": r"^TEST_", "$options": "i"}}]},
    "warehouse_sites": {"$or": [{"name": {"$regex": r"^TEST_", "$options": "i"}}, {"code": {"$regex": r"^TEST_", "$options": "i"}}]},
    "business_entities": {"legal_name": {"$regex": r"^PT Uji Provisioning", "$options": "i"}},
}
LABEL = {"warehouses": "gudang", "warehouse_sites": "site", "business_entities": "PT"}
FIELDS = ("is_test", "test_marked_at", "test_marked_by")


def _name(coll: str, d: dict) -> str:
    if coll == "business_entities":
        return f"{LABEL[coll]} {d.get('legal_name', '')}"
    return f"{LABEL[coll]} {d.get('code') or ''} {d.get('name', '')}".strip()


async def forward(P: G.Plan) -> None:
    P.step("tandai_data_uji", "data uji ditandai is_test (tidak dihapus)")
    now = now_iso()
    for c, q in RULES.items():
        async for d in db[c].find({**q, "is_test": {"$ne": True}}, {"_id": 0}):
            before, missing = G.snapshot(d, FIELDS)
            after = {"is_test": True, "test_marked_at": now, "test_marked_by": FLAG}
            if not ARGS.apply:
                P.change("tandai_data_uji", c, d["id"], label=_name(c, d), before=before, missing=missing, after=after)
                continue
            res = await db[c].update_one({"id": d["id"], "is_test": {"$ne": True}}, {"$set": after})
            if res.modified_count:
                P.change("tandai_data_uji", c, d["id"], label=_name(c, d), before=before, missing=missing, after=after)


async def undo(P: G.Plan) -> str:
    P.step("tandai_data_uji_undo", "penanda dicabut / nilai sebelum dipulihkan")
    try:
        rid, changes = await G.load_run(db, FLAG, ARGS.run_id)
    except G.Refused as exc:
        G.print_refusal_and_exit(exc)
    touched = set()
    for c in changes:
        touched.add((c["collection"], c["doc_id"]))
        if not ARGS.apply:
            P.change("tandai_data_uji_undo", c["collection"], c["doc_id"], label=c.get("label", ""),
                     before=c["after"], after={**c["before"], **{f: None for f in c["missing"]}})
            continue
        if await G.apply_restore(db, c):
            P.change("tandai_data_uji_undo", c["collection"], c["doc_id"], label=c.get("label", ""),
                     before=c["after"], after={**c["before"], **{f: None for f in c["missing"]}})
        else:
            print(f"  LEWAT {c.get('label') or c['doc_id']}: penanda sudah diubah sesudah skrip — tidak dikembalikan.")
    if not rid and not ARGS.run_id:   # tidak ada putaran berjejak: penanda putaran lama (sebelum FIX-7) dicabut berdasar penanda
        for coll in RULES:
            async for d in db[coll].find({"test_marked_by": FLAG}, {"_id": 0}):
                if (coll, d["id"]) in touched:
                    continue
                after = {"is_test": None, "test_marked_at": None, "test_marked_by": None}
                if not ARGS.apply:
                    P.change("tandai_data_uji_undo", coll, d["id"], label=_name(coll, d),
                             before={f: d.get(f) for f in FIELDS}, after=after, note="penanda putaran lama")
                    continue
                res = await db[coll].update_one({"id": d["id"], "test_marked_by": FLAG},
                                                {"$unset": {"is_test": "", "test_marked_at": "", "test_marked_by": ""}})
                if res.modified_count:
                    P.change("tandai_data_uji_undo", coll, d["id"], label=_name(coll, d),
                             before={f: d.get(f) for f in FIELDS}, after=after, note="penanda putaran lama")
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
    if ARGS.apply and P.changes:
        await P.save(db, ACTOR, kind="undo" if ARGS.undo else "apply", undone_run=undone)
    print(f"Selesai: {len(P.changes)} data {'diproses' if ARGS.apply else 'akan diproses (dry-run)'}.")
    await G.drain_tasks()


if __name__ == "__main__":
    asyncio.run(main())
