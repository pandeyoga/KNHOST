"""GN-15 — kontrak SSOT: resolver kebijakan tunggal + definisi stok fisik tunggal.

Usage: cd /app/backend && python ../audit/iterations/2026-10-02-P15-gn15-ssot/repro_gn15.py [repo_root]
In-process pada DB sintetis; nilai override uji dipasang lalu dikembalikan.
"""
import ast
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("..").resolve()
SERVICES = ("contract_service", "lot_service", "receiving_uom_service", "uom_rules_service")
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


def duplicate_get_settings():
    """Badan get_settings yang AST-nya identik di lebih dari satu service (selain delegasi tipis)."""
    bodies = {}
    for p in (ROOT / "backend/services").glob("*.py"):
        for node in ast.walk(ast.parse(p.read_text())):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "get_settings" and len(node.body) > 3:
                bodies.setdefault(ast.dump(ast.Module(body=node.body[1:], type_ignores=[])), []).append(p.name)
    return [v for v in bodies.values() if len(v) > 1]


async def main():
    import importlib
    from db import db
    from services import config_resolver as cr
    dups = duplicate_get_settings()
    check("GN-15", "tidak ada lagi salinan AST identik get_settings di services", not dups, dups)
    for name in SERVICES:
        mod = importlib.import_module(f"services.{name}")
        scope, defaults = mod.SETTINGS_SCOPE, mod.DEFAULT_SETTINGS
        key = next(iter(defaults))
        doc = await db.system_settings.find_one({"scope": scope}, {"_id": 0}) or {}
        glob = await mod.get_settings()
        ref = await cr.policy_settings(scope, defaults, "")
        check("GN-15", f"{name}: get_settings global = resolver tunggal", glob == ref, key)
        expected = doc.get(key) if doc.get(key) is not None else defaults[key]
        check("GN-15", f"{name}: fallback default→global untuk '{key}'", glob[key] == expected, f"{glob[key]} vs {expected}")
        ent = await mod.get_settings("ent_ksc")
        ovr = await cr.entity_overlay(scope, "ent_ksc")
        want = {k: (ovr[k] if k in ovr else glob[k]) for k in defaults}
        check("GN-15", f"{name}: override badan usaha menimpa global, sisanya ikut global",
              all(ent[k] == want[k] for k in defaults) and ent.get("entity_overrides") == sorted(k for k in ovr if k in defaults),
              ent.get("entity_overrides"))
        allx = await mod.get_settings("all")
        check("GN-15", f"{name}: entity 'all' = nilai global", {k: allx[k] for k in defaults} == {k: glob[k] for k in defaults})
    from services import analytics_catalog as cat
    from services import rfid_service as rf
    from services import roll_service as rs
    from services import stock_analytics_service as sa
    phys = set(rs.PHYSICAL_ROLL_STATUSES)
    check("GN-15", "Tanya KN/analitik memakai definisi stok fisik roll_service (termasuk wip)",
          set(cat.PHYSICAL_ROLL_STATUSES) == phys and "wip" in cat.PHYSICAL_ROLL_STATUSES, sorted(phys ^ set(cat.PHYSICAL_ROLL_STATUSES)))
    check("GN-15", "analitik stok (stock_analytics) = definisi roll_service", set(sa.PHYSICAL_STATUSES) == phys)
    check("GN-15", "kandidat tag RFID ⊇ stok fisik roll_service (RF-17)", phys <= set(rf.PHYSICAL_STATUSES))
    check("GN-15", "status reserved analitik ⊂ stok fisik", set(cat.RESERVED_ROLL_STATUSES) <= phys)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
