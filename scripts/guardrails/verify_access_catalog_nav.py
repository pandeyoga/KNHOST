"""FE-03 (review 2026-10-20) — katalog modul akses (`backend/access_modules.py`) selaras dengan menu frontend.

Peran kustom memperoleh menu dari `MODULE_CATALOG[*].nav`. Bila ID di sana basi atau hub diberikan
tanpa satu pun tabnya, pengguna berizin kehilangan pintu kerja (atau mendapat pintu mati). Gagal bila:
  1. ID nav modul tidak dikenal frontend (bukan menu/grup/hub/tab di navStructure/hubTabs, bukan view AppViewRouter);
  2. modul memberi item hub yang punya tab tampak, tetapi tidak satu pun tab tampaknya ikut modul itu.

Usage: python scripts/guardrails/verify_access_catalog_nav.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend" / "src"
sys.path.insert(0, str(ROOT / "backend"))


def frontend_index():
    nav = (FE / "config" / "navStructure.js").read_text(encoding="utf-8")
    hub_src = (FE / "config" / "hubTabs.js").read_text(encoding="utf-8")
    router = (FE / "AppViewRouter.jsx").read_text(encoding="utf-8")
    hubs = {}
    for m in re.finditer(r'^\s{2}"([\w-]+)":\s*\[(.*?)^\s{2}\],', hub_src, re.S | re.M):
        hubs[m.group(1)] = [(v, "hidden: true" in line) for line in m.group(2).splitlines()
                            for v in re.findall(r'view:\s*"([\w-]+)"', line)]
    item_hub = dict(re.findall(r'\bid:\s*"([\w-]+)"[^\n]*?\bhub:\s*"([\w-]+)"', nav))
    known = (set(re.findall(r'\b(?:id|groupId|view|hub):\s*"([\w-]+)"', nav + hub_src))
             | set(re.findall(r'activeView === "([\w-]+)"', router)) | set(hubs))
    return known, hubs, item_hub


def scan():
    from access_modules import MODULE_CATALOG
    known, hubs, item_hub = frontend_index()
    problems = []
    for mod in MODULE_CATALOG:
        nav = set(mod["nav"])
        for nid in sorted(nav - known):
            problems.append(f"[{mod['id']}] ID menu tidak dikenal frontend: {nid}")
        for nid in sorted(nav):
            hub = item_hub.get(nid) or (nid if nid in hubs else None)
            visible_tabs = [v for v, hidden in hubs.get(hub, []) if not hidden] if hub else []
            if visible_tabs and not (set(visible_tabs) & nav):
                problems.append(f"[{mod['id']}] hub {nid} diberikan tanpa satu pun tab tampaknya ({', '.join(visible_tabs)})")
    return problems


def main() -> int:
    problems = scan()
    for p in problems:
        print(p)
    print(f"verify_access_catalog_nav: {len(problems)} temuan")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
