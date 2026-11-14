"""FE-03 (review 2026-10-20) — katalog modul akses (`backend/access_modules.py`) selaras dengan menu frontend.

Peran kustom memperoleh menu dari `MODULE_CATALOG[*].nav`. Bila ID di sana basi atau hub diberikan
tanpa satu pun tabnya, pengguna berizin kehilangan pintu kerja (atau mendapat pintu mati). Gagal bila:
  1. ID nav modul tidak dikenal frontend (bukan menu/grup/hub/tab di navStructure/hubTabs, bukan view AppViewRouter);
  2. modul memberi item hub yang punya tab tampak, tetapi tidak satu pun tab tampaknya ikut modul itu;
  3. (KP-T9) tab tampak pada hub di grup Pengaturan (`settings-hub`) tidak ada di `nav` modul mana pun — peran kustom
     tidak pernah bisa mendapatkannya (dulu empat tab lolos karena penjaga hanya memeriksa id yang ADA di katalog);
  4. (KP-T9) modul yang memuat tab Pengaturan tidak memuat hub induknya DAN `settings-hub` — tabnya tidak terjangkau
     dari sidebar, atau grup Pengaturan disembunyikan untuk peran yang hanya memegang modul itu.

Usage: python scripts/guardrails/verify_access_catalog_nav.py [--self-test]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend" / "src"
sys.path.insert(0, str(ROOT / "backend"))


SETTINGS_GROUP = "settings-hub"


def settings_items(nav: str) -> dict:
    """KP-T9 — id item → id hub untuk butir grup sidebar `settings-hub` (grup Pengaturan)."""
    m = re.search(r'groupId:\s*"settings-hub"(.*?)\n\s{4}\],', nav, re.S)
    return dict(re.findall(r'\bid:\s*"([\w-]+)"[^\n]*?\bhub:\s*"([\w-]+)"', m.group(1))) if m else {}


def frontend_index():
    nav = (FE / "config" / "navStructure.js").read_text(encoding="utf-8")
    hub_src = (FE / "config" / "hubTabs.js").read_text(encoding="utf-8")
    router = (FE / "AppViewRouter.jsx").read_text(encoding="utf-8")
    return parse_frontend(nav, hub_src, router)


def parse_frontend(nav: str, hub_src: str, router: str):
    hubs = {}
    for m in re.finditer(r'^\s{2}"([\w-]+)":\s*\[(.*?)^\s{2}\],', hub_src, re.S | re.M):
        hubs[m.group(1)] = [(v, "hidden: true" in line) for line in m.group(2).splitlines()
                            for v in re.findall(r'view:\s*"([\w-]+)"', line)]
    item_hub = dict(re.findall(r'\bid:\s*"([\w-]+)"[^\n]*?\bhub:\s*"([\w-]+)"', nav))
    known = (set(re.findall(r'\b(?:id|groupId|view|hub):\s*"([\w-]+)"', nav + hub_src))
             | set(re.findall(r'activeView === "([\w-]+)"', router))
             | {v for lst in re.findall(r"\[([^\]]+)\]\.includes\(activeView\)", router) for v in re.findall(r'"([\w-]+)"', lst)}
             | set(hubs))
    return known, hubs, item_hub, settings_items(nav)


def scan(catalog=None, index=None):
    if catalog is None:
        from access_modules import MODULE_CATALOG as catalog
    known, hubs, item_hub, settings = index or frontend_index()
    problems = []
    for mod in catalog:
        nav = set(mod["nav"])
        for nid in sorted(nav - known):
            problems.append(f"[{mod['id']}] ID menu tidak dikenal frontend: {nid}")
        for nid in sorted(nav):
            hub = item_hub.get(nid) or (nid if nid in hubs else None)
            visible_tabs = [v for v, hidden in hubs.get(hub, []) if not hidden] if hub else []
            if visible_tabs and not (set(visible_tabs) & nav):
                problems.append(f"[{mod['id']}] hub {nid} diberikan tanpa satu pun tab tampaknya ({', '.join(visible_tabs)})")
    problems += scan_settings(catalog, hubs, settings)
    return problems


def scan_settings(catalog, hubs, settings) -> list:
    """KP-T9 — aturan (3) dan (4) untuk hub di grup Pengaturan."""
    problems = []
    dimuat = {v for mod in catalog for v in mod["nav"]}
    for item, hub in settings.items():
        for tab in [v for v, hidden in hubs.get(hub, []) if not hidden]:
            if tab not in dimuat:
                problems.append(f"[{item}] tab Pengaturan {tab} tidak ada di modul mana pun — peran kustom tidak bisa "
                                "mendapatkannya; masukkan ke modul pemilik izin endpoint layarnya")
    for mod in catalog:
        nav = set(mod["nav"])
        for item, hub in settings.items():
            tabs = [v for v, hidden in hubs.get(hub, []) if not hidden and v in nav]
            kurang = [x for x in (item, SETTINGS_GROUP) if x not in nav]
            if tabs and kurang:
                problems.append(f"[{mod['id']}] memuat tab Pengaturan ({', '.join(tabs)}) tanpa hub induknya: "
                                f"{', '.join(kurang)}")
    return problems


def self_test() -> int:
    """Bukti-merah aturan (1)–(4) dengan katalog & menu tiruan."""
    gagal = 0

    def cek(nama, ok):
        nonlocal gagal
        print(f"  {'✓' if ok else '✗'} {nama}")
        gagal += 0 if ok else 1

    nav = ('  {\n    type:    "group",\n    groupId: "settings-hub",\n    items: [\n'
           '      { id: "settings-a", label: "A", roles: ["admin"], hub: "settings-a" },\n'
           '      { id: "settings-b", label: "B", roles: ["admin"], hub: "settings-b" },\n    ],\n  },\n'
           '  { type: "standalone", id: "lain", label: "Lain", roles: ["admin"], hub: "lain" },\n')
    hub_src = ('export const HUB_TABS = {\n  "settings-a": [\n    { view: "tab-a1", label: "A1" },\n'
               '    { view: "tab-a2", label: "A2" },\n    { view: "tab-a3", label: "A3", hidden: true },\n  ],\n'
               '  "settings-b": [\n    { view: "tab-b1", label: "B1" },\n  ],\n'
               '  "lain": [\n    { view: "lain-1", label: "L1" },\n  ],\n};\n')
    router = '{activeView === "rute-x" && <X />}\n{["rute-y", "rute-z"].includes(activeView) && <Y />}\n'
    idx = parse_frontend(nav, hub_src, router)
    sah = [{"id": "m1", "nav": ["settings-hub", "settings-a", "tab-a1", "tab-a2"]},
           {"id": "m2", "nav": ["settings-hub", "settings-b", "tab-b1", "rute-z", "lain", "lain-1"]}]
    cek("katalog sah → 0 temuan", scan(sah, idx) == [])
    cek("butir grup Pengaturan terbaca (2 hub)", idx[3] == {"settings-a": "settings-a", "settings-b": "settings-b"})
    h = scan([{**sah[0], "nav": ["settings-hub", "settings-a", "tab-a1", "id-hantu"]}, sah[1]], idx)
    cek("(1) id tak dikenal → merah", any("tidak dikenal frontend: id-hantu" in x for x in h))
    h = scan([sah[0], {"id": "m2", "nav": ["settings-hub", "settings-b", "tab-b1", "lain"]}], idx)
    cek("(2) hub tanpa tab tampaknya → merah", any("hub lain diberikan tanpa" in x for x in h))
    h = scan([{"id": "m1", "nav": ["settings-hub", "settings-a", "tab-a1"]}, sah[1]], idx)
    cek("(3) tab tampak tanpa modul → tepat 1 temuan", h == [
        "[settings-a] tab Pengaturan tab-a2 tidak ada di modul mana pun — peran kustom tidak bisa mendapatkannya; "
        "masukkan ke modul pemilik izin endpoint layarnya"])
    cek("(3) tab tersembunyi tidak dituntut", not any("tab-a3" in x for x in scan(sah, idx)))
    h = scan([{"id": "m1", "nav": ["settings-a", "tab-a1", "tab-a2"]}, sah[1]], idx)
    cek("(4) tanpa settings-hub → merah", h == ["[m1] memuat tab Pengaturan (tab-a1, tab-a2) tanpa hub induknya: settings-hub"])
    h = scan([sah[0], {"id": "m2", "nav": ["settings-hub", "tab-b1"]}, {"id": "m3", "nav": ["settings-hub", "settings-b", "tab-b1"]}], idx)
    cek("(4) tanpa hub induk → merah", h == ["[m2] memuat tab Pengaturan (tab-b1) tanpa hub induknya: settings-b"])
    cek("rute `[...].includes(activeView)` dikenal", "rute-y" in idx[0] and "rute-z" in idx[0])
    print(f"  SELF-TEST {'HIJAU' if not gagal else 'MERAH'} ({gagal} gagal)")
    return gagal


def main() -> int:
    if "--self-test" in sys.argv:
        return 1 if self_test() else 0
    problems = scan()
    for p in problems:
        print(p)
    print(f"verify_access_catalog_nav: {len(problems)} temuan")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
