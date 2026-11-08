"""Audit B1 — matriks menu × peran MENURUT KODE (HANYA BACA kode; tidak menulis ke repo).

Meniru `roleCanSee` (`frontend/src/config/roles.js`) + `buildNavGroups`/`hubTabsForRole`
(`frontend/src/config/navigationConfig.js`) atas data `navStructure.js`, `hubTabs.js` dan `ROLE_NAV`.
Yang TIDAK ditiru: `accessBlocks` (izin server `view_resources`/`hidden_views` per akun) — sel yang
menurut kode tampil masih bisa disembunyikan server; hasil peramban yang menentukan status akhir.

Pakai:  PYTHONUTF8=1 python scripts/audit/b1_nav_matrix.py [--out <folder>] [--groups gudang,...]
Keluaran: <out>/nav_matrix.json + nav_matrix.md (cakupan gudang/kualitas/retur/pembelian/pengaturan).
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "frontend" / "src" / "config"
DEFAULT_OUT = Path(r"C:/Users/abc/AppData/Local/Temp/claude/d999a0fd1df8a838/"
                   r"4f003146-8d75-4e0b-9783-daa1d8e525b4/scratchpad/audit-b1/static")
ROLES = ["admin", "manager", "warehouse_admin", "warehouse", "sales", "sales_admin", "finance",
         "md", "md_quality", "qc", "sample_admin", "driver", "designer"]


def strip_comments(src):
    src = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def arr(s):
    return re.findall(r'"([^"]+)"', s or "")


def field(block, name):
    m = re.search(rf'\b{name}\s*:\s*"([^"]*)"', block)
    return m.group(1) if m else None


def roles_of(block):
    m = re.search(r"\broles\s*:\s*\[([^\]]*)\]", block)
    return arr(m.group(1)) if m else None


def parse_nav():
    src = strip_comments((CFG / "navStructure.js").read_text(encoding="utf-8"))
    body = src[src.index("export const NAV_STRUCTURE"):]
    entries, depth, start = [], 0, None
    i = body.index("[") + 1
    while i < len(body):
        c = body[i]
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start is not None:
                entries.append(body[start:i + 1])
                start = None
        elif c == "]" and depth == 0:
            break
        i += 1
    out = []
    for blk in entries:
        typ = field(blk, "type")
        if typ == "group":
            head = blk.split("items:")[0]
            items_src = blk.split("items:", 1)[1]
            items = []
            for line in re.findall(r"\{[^{}]*\}", items_src):
                if field(line, "type") == "heading":
                    continue
                items.append({"id": field(line, "id"), "label": field(line, "label"), "roles": roles_of(line),
                              "hub": field(line, "hub"), "view": field(line, "view"),
                              "comingSoon": "comingSoon: true" in line})
            out.append({"type": "group", "groupId": field(head, "groupId"), "label": field(head, "label"),
                        "roles": roles_of(head), "items": items})
        else:
            out.append({"type": "standalone", "id": field(blk, "id"), "label": field(blk, "label"),
                        "roles": roles_of(blk), "hub": field(blk, "hub"), "view": field(blk, "view")})
    return out


def parse_hub_tabs():
    src = strip_comments((CFG / "hubTabs.js").read_text(encoding="utf-8"))
    tabs = {}
    for m in re.finditer(r'"([a-z0-9-]+)"\s*:\s*\[(.*?)\n\s*\],', src, flags=re.S):
        rows = []
        for line in re.findall(r"\{[^{}]*\}", m.group(2)):
            rows.append({"view": field(line, "view"), "label": field(line, "label"), "roles": roles_of(line),
                         "hidden": "hidden: true" in line})
        tabs[m.group(1)] = rows
    return tabs


def parse_role_nav():
    src = strip_comments((CFG / "roles.js").read_text(encoding="utf-8"))
    body = src[src.index("export const ROLE_NAV"):src.index("export function setAccessContext")]
    out = {}
    for m in re.finditer(r"\n  ([a-z_]+): \{(.*?)\n  \},", body, flags=re.S):
        blk = m.group(2)
        inh = re.search(r'inherit\s*:\s*(null|"([a-z_]+)")', blk)
        add = re.search(r"add\s*:\s*\[(.*?)\]", blk, flags=re.S)
        rem = re.search(r"remove\s*:\s*\[(.*?)\]", blk, flags=re.S)
        out[m.group(1)] = {"inherit": inh.group(2) if inh and inh.group(2) else None,
                           "add": arr(add.group(1) if add else ""), "remove": arr(rem.group(1) if rem else "")}
    return out


ROLE_NAV = parse_role_nav()
HUB_TABS = parse_hub_tabs()


def role_can_see(roles, role, id_, depth=0):
    rule = ROLE_NAV.get(role)
    if rule and id_ and id_ in rule["remove"]:
        return False
    if roles is None:
        return True
    if role in roles:
        return True
    if not rule:
        return False
    if id_ and id_ in rule["add"]:
        return True
    if rule["inherit"] and depth < 3:
        return role_can_see(roles, rule["inherit"], id_, depth + 1)
    return False


def hub_tabs_for_role(hub, role):
    return [t for t in HUB_TABS.get(hub, []) if not t["hidden"] and role_can_see(t["roles"], role, t["view"])]


def hub_without_tabs(item, role):
    if not item.get("hub") or not any(not t["hidden"] for t in HUB_TABS.get(item["hub"], [])):
        return False
    return not hub_tabs_for_role(item["hub"], role)


def matrix(groups_filter=None):
    nav = parse_nav()
    rows = []
    for e in nav:
        if e["type"] == "standalone":
            entries = [(None, e)]
            gid = e["id"]
        else:
            entries = [(e, it) for it in e["items"]]
            gid = e["groupId"]
        if groups_filter and gid not in groups_filter:
            continue
        for grp, it in entries:
            cell = {}
            for r in ROLES:
                own = role_can_see(grp["roles"], r, grp["groupId"]) if grp else True
                vis = (own or False) and role_can_see(it["roles"], r, it["id"]) and not hub_without_tabs(it, r)
                tabs = [t["label"] for t in hub_tabs_for_role(it["hub"], r)] if (vis and it.get("hub")) else []
                cell[r] = {"menu": bool(vis), "tabs": tabs}
            rows.append({"group": grp["label"] if grp else "(lepas)", "id": it["id"], "label": it["label"],
                         "hub": it.get("hub"), "comingSoon": it.get("comingSoon", False), "roles": cell,
                         "all_tabs": [t["label"] for t in HUB_TABS.get(it.get("hub") or "", []) if not t["hidden"]]})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--groups", default="")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = matrix(set(filter(None, a.groups.split(","))) or None)
    (out / "nav_matrix.json").write_text(json.dumps({"role_nav": ROLE_NAV, "rows": rows}, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    lines = ["| Grup | Menu (id) | " + " | ".join(ROLES) + " |", "|---|---|" + "---|" * len(ROLES)]
    for r in rows:
        cells = []
        for role in ROLES:
            c = r["roles"][role]
            cells.append(("✓" + (f" ({len(c['tabs'])}/{len(r['all_tabs'])} tab)" if r["all_tabs"] else "")) if c["menu"] else "–")
        lines.append(f"| {r['group']} | {r['label']} (`{r['id']}`) | " + " | ".join(cells) + " |")
    (out / "nav_matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
