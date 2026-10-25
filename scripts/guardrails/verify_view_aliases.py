#!/usr/bin/env python3
"""INV-NAV-02 — ALIAS LAYAR (layar duplikat = tautan) TIDAK BOLEH MEMUTUS PINTU ATAU HAK (fase 3 · P1).

MASALAH YANG DICEGAH
====================
Keputusan pemilik 26 Okt: layar duplikat tidak dihapus, melainkan menjadi ALIAS ke layar utama (+ preset tab/mode)
lewat registri `frontend/src/config/viewAliases.js`. Alamat lama hidup di banyak tempat yang TIDAK ikut diubah:
deep link `?view=`, notifikasi & giliran backend (TURN_MAP), papan antrean (`approval_backlog_service` view
target, mis. `cs-design-gallery`), bookmark, dan uji. Alias yang salah tulis memutus semua pintu itu tanpa galat.

ATURAN (statik):
  A. `to` WAJIB layar nyata: dirender `AppViewRouter.jsx` (`activeView === "<to>"`) DAN ada di menu
     (`hubTabs.js`/`navStructure.js`).
  B. Tanpa rantai & tanpa alias-ke-diri-sendiri (`to` bukan kunci alias lain).
  C. Alias non-`legacy` WAJIB tetap punya RUTE CADANGAN `activeView === "<lama>"` di router — guardrail lain
     (`verify_desk_targets`, `verify_home_kpi`, `verify_approval_queues`, `verify_access_catalog_nav`) dan backend
     masih menunjuk id lama. `legacy: true` = nama lama yang memang tak pernah punya layar (mis. `approvals`).
  D. `nav` (bila diisi) WAJIB menu yang memuat `to` (item ber-view `to`, atau hub yang punya tab `to`).
  E. Peran bawaan yang dulu boleh membuka id lama ⊆ peran yang boleh membuka `to` (roles tab hub + overlay
     `ROLE_NAV`). Id lama yang sudah dicabut dari menu diperiksa oleh uji jangkauan peran berbaseline
     (`frontend/src/config/__tests__/roleReach.test.js`).
  F. `since` WAJIB diisi (asal keputusan D-xx / S14) supaya alias bisa ditelusuri.

Pakai:
    python scripts/guardrails/verify_view_aliases.py
    python scripts/guardrails/verify_view_aliases.py --self-test
"""
from __future__ import annotations

import os
import re
import sys
from typing import Dict, List, Set

sys.path.insert(0, os.path.dirname(__file__))
from _common import FRONTEND, Guard, G, R, X  # noqa: E402

SRC = FRONTEND / "src"
ALIASES = SRC / "config" / "viewAliases.js"
ROUTER = SRC / "AppViewRouter.jsx"
HUBTABS = SRC / "config" / "hubTabs.js"
NAVSTRUCT = SRC / "config" / "navStructure.js"
ROLES = SRC / "config" / "roles.js"


def _strip_line_comments(s: str) -> str:
    return re.sub(r"(^|\s)//[^\n]*", r"\1", s)


def parse_aliases(text: str) -> Dict[str, dict]:
    m = re.search(r"export const VIEW_ALIASES\s*=\s*\{(.*?)\n\};", text, re.S)
    if not m:
        return {}
    body = _strip_line_comments(m.group(1))
    out: Dict[str, dict] = {}
    i = 0
    key_rx = re.compile(r'\s*"?([\w-]+)"?\s*:\s*\{')
    while True:
        km = key_rx.search(body, i)
        if not km:
            break
        depth, j = 1, km.end()
        while j < len(body) and depth:
            depth += {"{": 1, "}": -1}.get(body[j], 0)
            j += 1
        blk = body[km.end():j - 1]
        flat = re.sub(r"preset\s*:\s*\{[^}]*\}", "", blk)
        get = lambda k: (re.search(rf'\b{k}\s*:\s*"([^"]*)"', flat) or [None, None])[1]  # noqa: E731
        out[km.group(1)] = {
            "to": get("to"), "nav": get("nav"), "since": get("since"), "label": get("label"),
            "legacy": bool(re.search(r"\blegacy\s*:\s*true", flat)),
        }
        i = j
    return out


def router_views(text: str) -> Set[str]:
    views = set(re.findall(r'activeView\s*===\s*"([\w-]+)"', text))
    for lst in re.findall(r"\[([^\]]+)\]\.includes\(activeView\)", text):
        views.update(re.findall(r'"([\w-]+)"', lst))
    return views


def hub_tabs(text: str) -> Dict[str, List[dict]]:
    hubs: Dict[str, List[dict]] = {}
    for m in re.finditer(r'^\s{2}"([\w-]+)":\s*\[(.*?)^\s{2}\],', text, re.S | re.M):
        tabs = []
        for t in re.finditer(r'\{\s*view:\s*"([\w-]+)"[^}]*?roles:\s*\[([^\]]*)\]', m.group(2)):
            tabs.append({"view": t.group(1), "roles": re.findall(r'"([\w-]+)"', t.group(2))})
        hubs[m.group(1)] = tabs
    return hubs


def menu_ids(nav_text: str, hubs: Dict[str, List[dict]]) -> Dict[str, Set[str]]:
    """menu id → view yang dicakupnya (item `view`/`id`, atau semua tab hub-nya)."""
    out: Dict[str, Set[str]] = {}
    for m in re.finditer(r'\bid:\s*"([\w-]+)"([^\n]*)', nav_text):
        mid, rest = m.group(1), m.group(2)
        hub = re.search(r'\bhub:\s*"([\w-]+)"', rest)
        view = re.search(r'\bview:\s*"([\w-]+)"', rest)
        covered = {t["view"] for t in hubs.get(hub.group(1), [])} if hub else set()
        covered.add(view.group(1) if view else mid)
        out.setdefault(mid, set()).update(covered)
    # standalone multi-baris (id/hub/view di baris terpisah)
    for blk in re.findall(r'type:\s*"standalone",(.*?)\n\s*\},?\n', nav_text, re.S):
        idm = re.search(r'\bid:\s*"([\w-]+)"', blk)
        if not idm:
            continue
        hub = re.search(r'\bhub:\s*"([\w-]+)"', blk)
        view = re.search(r'\bview:\s*"([\w-]+)"', blk)
        covered = {t["view"] for t in hubs.get(hub.group(1), [])} if hub else set()
        if view:
            covered.add(view.group(1))
        out.setdefault(idm.group(1), set()).update(covered)
    return out


def role_nav(text: str) -> Dict[str, dict]:
    m = re.search(r"export const ROLE_NAV\s*=\s*\{(.*?)\n\};", text, re.S)
    if not m:
        return {}
    out = {}
    for rm in re.finditer(r"(\w+):\s*\{(.*?)\n  \},", m.group(1), re.S):
        blk = re.sub(r"//[^\n]*", "", rm.group(2))
        inh = re.search(r'inherit:\s*"([^"]+)"', blk)
        add = re.search(r"add:\s*\[(.*?)\]", blk, re.S)
        rem = re.search(r"remove:\s*\[(.*?)\]", blk, re.S)
        out[rm.group(1)] = {
            "inherit": inh.group(1) if inh else None,
            "add": set(re.findall(r'"([\w-]+)"', add.group(1) if add else "")),
            "remove": set(re.findall(r'"([\w-]+)"', rem.group(1) if rem else "")),
        }
    return out


def role_ids(text: str) -> List[str]:
    m = re.search(r"export const ROLE_REGISTRY\s*=\s*\{(.*?)\n\};", text, re.S)
    return re.findall(r"^  (\w+):\s*\{", m.group(1), re.M) if m else []


def can_see(role: str, roles: List[str], ident: str, rnav: Dict[str, dict], depth: int = 0) -> bool:
    rule = rnav.get(role) or {}
    if ident in rule.get("remove", ()):
        return False
    if role in roles:
        return True
    if ident in rule.get("add", ()):
        return True
    inh = rule.get("inherit")
    return bool(inh and depth < 3 and can_see(inh, roles, ident, rnav, depth + 1))


def analyze(aliases: Dict[str, dict], routed: Set[str], hubs: Dict[str, List[dict]],
            menus: Dict[str, Set[str]], rnav: Dict[str, dict], roles: List[str]) -> List[str]:
    out: List[str] = []
    tab_roles = {t["view"]: t["roles"] for tabs in hubs.values() for t in tabs}
    in_menu = set(tab_roles) | {v for vs in menus.values() for v in vs} | set(menus)
    for old, a in sorted(aliases.items()):
        to = a.get("to")
        if not to:
            out.append(f"alias `{old}` tanpa `to`.")
            continue
        if not a.get("since"):
            out.append(f"alias `{old}` tanpa `since` (asal keputusan D-xx/S14) — tak bisa ditelusuri.")
        if to == old or to in aliases:
            out.append(f"alias `{old}` → `{to}` berantai/menunjuk diri sendiri — `to` harus layar utama, bukan alias.")
        if to not in routed:
            out.append(f"alias `{old}` → `{to}` yang TIDAK dirender AppViewRouter (layar hantu).")
        if to not in in_menu:
            out.append(f"alias `{old}` → `{to}` yang tidak ada di menu (hubTabs/navStructure) — tak ada sorotan/hak.")
        if not a.get("legacy") and old not in routed:
            out.append(f"alias `{old}` kehilangan RUTE CADANGAN `activeView === \"{old}\"` di AppViewRouter — "
                       "notifikasi/papan/guardrail yang masih menunjuk id lama mendarat di layar kosong.")
        nav = a.get("nav")
        if nav and to not in menus.get(nav, set()):
            out.append(f"alias `{old}`: `nav: \"{nav}\"` bukan menu yang memuat `{to}`.")
        if old in tab_roles and to in tab_roles:
            lost = [r for r in roles if can_see(r, tab_roles[old], old, rnav) and not can_see(r, tab_roles[to], to, rnav)]
            if lost:
                out.append(f"alias `{old}` → `{to}`: peran {lost} dulu bisa membuka `{old}` tetapi TIDAK bisa membuka "
                           f"`{to}` — hak hilang diam-diam. Tambah peran itu di tab tujuan (catat di §6 rencana fase 3).")
    return out


def main() -> int:
    g = Guard("INV-NAV-02", "alias layar tidak memutus pintu/hak (registri config/viewAliases.js)")
    for p in (ALIASES, ROUTER, HUBTABS, NAVSTRUCT, ROLES):
        if not p.exists():
            g.add(f"berkas tidak ditemukan: {p.relative_to(FRONTEND.parent)}")
    if g.violations:
        return g.finish()
    aliases = parse_aliases(ALIASES.read_text(encoding="utf-8"))
    if not aliases:
        g.add("VIEW_ALIASES tidak terbaca (format berubah?) — perbarui guardrail ini.")
        return g.finish()
    hubs = hub_tabs(HUBTABS.read_text(encoding="utf-8"))
    menus = menu_ids(NAVSTRUCT.read_text(encoding="utf-8"), hubs)
    roles_txt = ROLES.read_text(encoding="utf-8")
    hasil = analyze(aliases, router_views(ROUTER.read_text(encoding="utf-8")), hubs, menus,
                    role_nav(roles_txt), role_ids(roles_txt))
    g.bump(len(aliases) * 6)
    print(f"  alias terdaftar: {len(aliases)} ({sum(1 for a in aliases.values() if a['legacy'])} legacy)")
    for h in hasil:
        g.add(h)
    return g.finish()


def self_test() -> int:
    gagal = 0

    def cek(nama, ok):
        nonlocal gagal
        print(f"  {'✓' if ok else '✗'} {nama}")
        gagal += 0 if ok else 1

    src = ('export const VIEW_ALIASES = {\n'
           '  approvals: { to: "approval-inbox", legacy: true, since: "S14" },\n'
           '  // komentar: "x": { to: "y" }\n'
           '  "my-approvals": {\n    to: "approval-inbox", nav: "approval-inbox",\n'
           '    preset: { tab: "matrix", since: "palsu" }, since: "D-06",\n  },\n};\n')
    al = parse_aliases(src)
    cek("urai entri satu baris & multi-baris (preset bersarang diabaikan)",
        al == {"approvals": {"to": "approval-inbox", "nav": None, "since": "S14", "label": None, "legacy": True},
               "my-approvals": {"to": "approval-inbox", "nav": "approval-inbox", "since": "D-06", "label": None, "legacy": False}})
    hubs = {"approval-inbox": [{"view": "approval-inbox", "roles": ["manager", "admin"]},
                               {"view": "my-approvals", "roles": ["manager", "admin"]}]}
    menus = {"approval-inbox": {"approval-inbox", "my-approvals"}}
    routed = {"approval-inbox", "my-approvals"}
    cek("registri sah → hijau", analyze(al, routed, hubs, menus, {}, ["admin", "manager", "sales"]) == [])
    cek("rute cadangan hilang → merah",
        any("RUTE CADANGAN" in h for h in analyze(al, {"approval-inbox"}, hubs, menus, {}, ["admin"])))
    cek("tujuan hantu → merah",
        any("TIDAK dirender" in h for h in analyze({"x": {"to": "zz", "since": "D-1", "legacy": True}}, routed, hubs, menus, {}, [])))
    cek("rantai alias → merah",
        any("berantai" in h for h in analyze({"a": {"to": "b", "since": "D", "legacy": True},
                                              "b": {"to": "approval-inbox", "since": "D", "legacy": True}}, routed | {"b"}, hubs, menus, {}, [])))
    hubs2 = {"approval-inbox": [{"view": "approval-inbox", "roles": ["admin"]},
                                {"view": "my-approvals", "roles": ["manager", "admin"]}]}
    cek("peran hilang (manager) → merah",
        any("hak hilang" in h for h in analyze(al, routed, hubs2, menus, {}, ["admin", "manager"])))
    cek("peran lewat overlay ROLE_NAV dihitung",
        analyze(al, routed, hubs2, menus, {"manager": {"inherit": None, "add": {"approval-inbox"}, "remove": set()}},
                ["admin", "manager"]) == [])
    cek("nav bukan menu tujuan → merah",
        any("bukan menu" in h for h in analyze({"q": {"to": "approval-inbox", "nav": "ledger", "since": "D", "legacy": True}},
                                               routed, hubs, menus, {}, [])))
    print(f"{G if not gagal else R}  SELF-TEST {'HIJAU' if not gagal else 'MERAH'} ({gagal} gagal){X}")
    return gagal


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(1 if self_test() else 0)
    raise SystemExit(main())
