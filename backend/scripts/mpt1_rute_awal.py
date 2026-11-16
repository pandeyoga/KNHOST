"""MP-T1 (K-71) — rute awal untuk artikel yang belum punya rute di sebuah PT, dari data lama.

Sumber usulan (sama dengan tombol "Usulkan dari data lama" di Master Produk › Rute, `product_route_service.suggest`):
  1. rantai resep proses yang berakhir di varian artikel → rute makloon per tahap (mitra bawaan resep);
  2. BOM produksi aktif berhasil varian artikel → rute produksi sendiri;
  3. sumber restock artikel "supplier"/"keduanya" → rute beli dari pemasok (pemasok diisi hanya bila tunggal).
Tiap usulan diperiksa aturan rute yang sama dengan layar; usulan yang ditolak aturan dilaporkan, tidak dipaksa.
Artikel yang sudah punya rute aktif di PT itu dilewati, sehingga skrip aman dijalankan ulang.

BAWAAN = dry-run (tidak menulis apa pun). Menjalankan di data nyata = titik henti H3 (cadangan dulu, mode coba, tinjau).

Pakai (di dalam kontainer backend):
  python /app/backend/scripts/mpt1_rute_awal.py                       # dry-run semua PT
  python /app/backend/scripts/mpt1_rute_awal.py --entity ent_ksc      # dry-run satu PT
  python /app/backend/scripts/mpt1_rute_awal.py --apply               # tulis
  python /app/backend/scripts/mpt1_rute_awal.py --undo --apply        # hapus rute awal yang belum pernah diubah
Produksi: `… --db kainnusantara --production --backup-file <kainnusantara-YYYY-MM-DD_HHMM.archive.gz> [--apply]`.
"""
import asyncio
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

ACTOR = "Pembuat rute awal (MP-T1)"
FLAG = "mpt1_rute_awal"


async def jalankan(*, apply: bool, entity_id: str = "",
                   template_ids: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    from db import db
    from services import product_route_service as svc
    if entity_id:
        entities = [entity_id]
    else:
        entities = [e["id"] for e in await db.business_entities.find({"status": {"$ne": "archived"}},
                                                                      {"_id": 0, "id": 1}).to_list(200)]
    q: Dict[str, Any] = {"status": {"$ne": "archived"}}
    if template_ids:
        q["id"] = {"$in": list(template_ids)}
    templates = await db.product_templates.find(q, {"_id": 0, "id": 1, "name": 1, "stage": 1}).to_list(None)
    hasil: Dict[str, Any] = {"akan_dibuat": 0, "dibuat": 0, "dilewati_sudah_ada": 0, "ditolak_aturan": 0,
                             "tanpa_usulan": 0, "rincian": []}
    for ent in entities:
        for tpl in templates:
            if await db[svc.COLL].find_one({"entity_id": ent, "template_id": tpl["id"], "status": "active"},
                                           {"_id": 1}):
                hasil["dilewati_sudah_ada"] += 1
                continue
            usulan = await svc.suggest(tpl["id"], ent)
            if not usulan:
                hasil["tanpa_usulan"] += 1
                continue
            for u in usulan:
                try:
                    await svc.validate(tpl, {"steps": u["steps"]}, ent)
                except svc.RouteError as exc:
                    hasil["ditolak_aturan"] += 1
                    hasil["rincian"].append({"pt": ent, "artikel": tpl.get("name"), "rute": u["name"],
                                             "hasil": f"ditolak: {exc}"})
                    continue
                hasil["akan_dibuat"] += 1
                hasil["rincian"].append({"pt": ent, "artikel": tpl.get("name"), "rute": u["name"],
                                         "hasil": "dibuat" if apply else "akan dibuat"})
                if apply:
                    await svc.create(tpl["id"], {"name": u["name"], "steps": u["steps"]}, {"name": ACTOR}, ent,
                                     origin="rute_awal", origin_ref=u.get("origin_ref") or {})
                    hasil["dibuat"] += 1
    return hasil


async def batalkan(*, apply: bool, entity_id: str = "") -> int:
    """Hapus rute awal yang belum pernah diubah sejak dibuat skrip ini (riwayat hanya 'dibuat')."""
    from db import db
    q: Dict[str, Any] = {"origin": "rute_awal", "created_by": ACTOR, "history": {"$size": 1}}
    if entity_id:
        q["entity_id"] = entity_id
    n = await db.product_routes.count_documents(q)
    if apply and n:
        await db.product_routes.delete_many(q)
    return n


def _args():
    from services import data_fix_guard as G
    ap = G.build_parser(__doc__.splitlines()[0], db_default=os.environ.get("DB_NAME", ""))
    ap.add_argument("--entity", default="", help="satu PT saja (bawaan: semua PT aktif)")
    return G.parse_and_guard(ap, FLAG)


async def main(args) -> int:
    from services import data_fix_guard as G
    G.banner(args)
    if args.undo:
        n = await batalkan(apply=args.apply, entity_id=args.entity)
        print(f"rute awal yang {'dihapus' if args.apply else 'akan dihapus'}: {n}")
        return 0
    hasil = await jalankan(apply=args.apply, entity_id=args.entity)
    show: List[Dict[str, Any]] = hasil["rincian"][: args.show or None]
    for r in show:
        print(f"  [{r['pt']}] {r['artikel']} — {r['rute']}: {r['hasil']}")
    print({k: v for k, v in hasil.items() if k != "rincian"})
    await G.drain_tasks()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(_args())))
