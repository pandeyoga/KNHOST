"""PELATIHAN KEUANGAN (18 Nov 2026) — siapkan data latihan per peserta lewat ENDPOINT RESMI.

Tiap peserta mendapat akun Finance sendiri (`finance.latihNN@kainnusantara.id`, sandi `demo12345`, hanya PT Sukacita),
pelanggan & pemasok latihan sendiri ("Latihan NN · …"), lalu dokumen awal tiap skenario (SO terkirim belum dibayar,
tagihan supplier, dst. — lihat `scripts/latih_keuangan/*.py`). Aman dijalankan ulang: yang sudah ada dilewati.

  python scripts/seed_pelatihan_keuangan_kn.py                 # 6 peserta (01–06)
  python scripts/seed_pelatihan_keuangan_kn.py --peserta 10    # 01–10
  python scripts/seed_pelatihan_keuangan_kn.py --kartu         # hanya cetak Kartu Peserta (tanpa membuat apa pun)
  python scripts/seed_pelatihan_keuangan_kn.py --nonaktifkan   # sesudah pelatihan: nonaktifkan akun latihan

Syarat: data demo lengkap (`deploy/setup_demo_lengkap.sh` / `scripts/restore_local_demo.sh`).
"""
import argparse
import asyncio
import importlib
import json
import pkgutil
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402
from scripts.demo_api import Api, ApiError  # noqa: E402

import scripts.latih_keuangan as pkg  # noqa: E402
from scripts.latih_keuangan.konteks import TANDA, LatihCtx, Peserta  # noqa: E402

FLAG = "pelatihan_keuangan"


def log(msg: str) -> None:
    print(msg, flush=True)


def preps():
    out = []
    for m in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda x: x.name):
        if m.name in ("konteks",):
            continue
        mod = importlib.import_module(f"scripts.latih_keuangan.{m.name}")
        for key, fn in getattr(mod, "PREPS", []):
            out.append((f"{m.name}:{key}", fn))   # tanpa titik: kunci jadi nama field Mongo
    return out


async def kartu(n: int) -> None:
    state = (await db.migrations.find_one({"id": FLAG}, {"_id": 0}) or {}).get("peserta", {})
    log("\n================ KARTU PESERTA (sandi semua: demo12345 · PT Sukacita) ================")
    for i in range(1, n + 1):
        p = Peserta(i)
        done = state.get(p.kode, {})
        log(f"\nPeserta {p.kode} — {p.email}")
        for key, val in done.items():
            if isinstance(val, dict):
                show = {k: v for k, v in val.items() if not k.endswith("_id")}
                log(f"  {key:<34} {json.dumps(show, ensure_ascii=False)}")


async def nonaktifkan() -> None:
    r = await db.users.update_many({"training_batch": TANDA}, {"$set": {"status": "inactive", "updated_at": now_iso()}})
    await db.sessions.delete_many({"user_id": {"$in": [u["id"] for u in await db.users.find(
        {"training_batch": TANDA}, {"_id": 0, "id": 1}).to_list(500)]}})
    log(f"Akun latihan dinonaktifkan: {r.modified_count}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--peserta", type=int, default=6)
    ap.add_argument("--mulai", type=int, default=1, help="nomor peserta pertama (mis. --mulai 3 --peserta 3 = hanya 03)")
    ap.add_argument("--kartu", action="store_true")
    ap.add_argument("--nonaktifkan", action="store_true")
    ap.add_argument("--hanya", default="", help="jalankan prep tertentu saja (awalan kunci, mis. a_dasar:so_lunas)")
    a = ap.parse_args()
    if a.nonaktifkan:
        return await nonaktifkan()
    if a.kartu:
        return await kartu(a.peserta)
    if not await db.migrations.find_one({"id": "demo_lengkap_master"}):
        sys.exit("Jalankan dulu data demo lengkap (deploy/setup_demo_lengkap.sh).")
    cst = (await db.business_entities.find_one({"doc_prefix": "CST"}, {"_id": 0, "id": 1}))["id"]
    api = Api()
    lc = LatihCtx(api, cst)
    failed = []
    steps = [s for s in preps() if s[0].startswith(a.hanya)]
    try:
        for i in range(a.mulai, a.peserta + 1):
            p = Peserta(i)
            state = (await db.migrations.find_one({"id": FLAG}, {"_id": 0}) or {}).get("peserta", {})
            p.kartu = state.get(p.kode, {})
            log(f"— Peserta {p.kode} ({p.email})")
            for key, fn in steps:
                if key in p.kartu:
                    continue
                try:
                    res = await fn(lc, p)
                    p.kartu[key] = res or {}
                    await db.migrations.update_one({"id": FLAG}, {"$set": {f"peserta.{p.kode}.{key}": p.kartu[key],
                                                                           "updated_at": now_iso()}}, upsert=True)
                    log(f"   ✓ {key}: {json.dumps({k: v for k, v in (res or {}).items() if not k.endswith('_id')}, ensure_ascii=False)}")
                except Exception as e:  # noqa: BLE001
                    failed.append(f"{p.kode}:{key}")
                    log(f"   ✗ {key}: {e}")
                    if not isinstance(e, ApiError):
                        traceback.print_exc()
    finally:
        await asyncio.sleep(2)
        await api.close()
    await kartu(a.peserta)
    if failed:
        sys.exit(f"\nSelesai dengan {len(failed)} langkah gagal: {', '.join(failed)} (jalankan ulang setelah diperbaiki)")
    log("\nSELESAI — data latihan keuangan siap.")


if __name__ == "__main__":
    asyncio.run(main())
