"""Inventaris IA menyeluruh: menu → tab hub → tab di halaman → sub-tab (rekursif via import),
plus peta endpoint tulis (POST/PUT/PATCH/DELETE) per layar untuk mendeteksi data yang dikelola di >1 tempat.
Output: /app/docs/audit/ia/IA_INVENTORY.json + ringkasan di stdout."""
import json
import os
import re
from collections import defaultdict

SRC = "/app/frontend/src"
OUT = "/app/docs/audit/ia"


def read(p):
    with open(p, encoding="utf8") as f:
        return f.read()


def resolve(base_file, spec):
    if spec.startswith("@/"):
        base = os.path.join(SRC, spec[2:])
    elif spec.startswith("."):
        base = os.path.normpath(os.path.join(os.path.dirname(base_file), spec))
    else:
        return None
    for cand in (base, base + ".jsx", base + ".js", os.path.join(base, "index.jsx"), os.path.join(base, "index.js")):
        if os.path.isfile(cand):
            return cand
    return None


IMPORT_RE = re.compile(r'(?:import\s+(?:[\w{}\s,*]+)\s+from\s+|import\()\s*["\']([^"\']+)["\']')
TAB_ARR_RE = re.compile(r'const\s+(\w*(?:TAB|Tab|tab|SECTION|MODE|PANE|VIEWS|STEPS|KINDS)\w*)\s*=\s*\[(.*?)\n\s*\];', re.S)
ENTRY_RE = re.compile(r'\{\s*(?:key|id|k|view|t)\s*:\s*["\']([\w.-]+)["\']\s*,\s*(?:label|title|name)\s*:\s*["\']([^"\']+)["\']')
PAIR_RE = re.compile(r'\[\s*["\']([\w-]+)["\']\s*,\s*["\']([^"\']+)["\']\s*\]')
WRITE_RE = re.compile(r'axios\.(post|put|patch|delete)\(\s*[`"\']\$\{API\}(/[^`"\'?$]*)')
API_FN_RE = re.compile(r'(post|put|patch|delete)\w*\(\s*[`"\']\$\{API\}(/[^`"\'?$]*)')
SKIP_COMPONENTS = ("components/ui/", "KNSelect", "FormModal", "DetailModal", "KNPager", "PagedRows")


def norm_ep(ep):
    ep = re.sub(r"/\$\{[^}]+\}", "/:id", ep)
    return re.sub(r"/+$", "", ep)


def tabs_in(text):
    out = []
    for name, body in TAB_ARR_RE.findall(text):
        ents = ENTRY_RE.findall(body) or PAIR_RE.findall(body)
        if 2 <= len(ents) <= 20:
            out.append({"var": name, "tabs": [{"id": a, "label": b} for a, b in ents]})
    return out


def scan(file, depth, seen):
    if file in seen or depth > 4 or any(s in file for s in SKIP_COMPONENTS):
        return None
    seen.add(file)
    text = read(file)
    node = {"file": file.replace(SRC + "/", ""), "tabs": tabs_in(text),
            "writes": sorted({f"{m.upper()} {norm_ep(e)}" for m, e in WRITE_RE.findall(text) + API_FN_RE.findall(text)}),
            "children": []}
    for spec in IMPORT_RE.findall(text):
        r = resolve(file, spec)
        if r and r.startswith(os.path.join(SRC, "features")) or (r and "/components/" in r and "ui/" not in r):
            ch = scan(r, depth + 1, seen)
            if ch and (ch["tabs"] or ch["writes"] or ch["children"]):
                node["children"].append(ch)
    return node


def nav():
    ns, ht = read(f"{SRC}/config/navStructure.js"), read(f"{SRC}/config/hubTabs.js")
    hubs, cur = {}, None
    for line in ht.splitlines():
        m = re.match(r'\s*"([\w-]+)": \[', line)
        if m:
            cur = m.group(1); hubs[cur] = []
        v = re.search(r'view:\s*"([\w-]+)",\s*label:\s*"([^"]+)",\s*roles:\s*\[([^\]]*)\]', line)
        if v and cur:
            hubs[cur].append({"view": v.group(1), "label": v.group(2), "roles": re.findall(r'"(\w+)"', v.group(3))})
    entries, group = [], "(standalone)"
    for line in ns.splitlines():
        g = re.search(r'groupId:\s*"([\w-]+)"', line)
        if g:
            group = g.group(1)
        lab = re.search(r'^\s*label:\s*"([^"]+)"', line)
        if lab and group != "(standalone)" and entries and entries[-1].get("_grp") != group:
            entries.append({"_grp": group, "group_label": lab.group(1)})
        m = re.search(r'id:\s*"([\w-]+)",\s*label:\s*"([^"]+)"(.*)', line)
        if m:
            hub = re.search(r'hub:\s*"([\w-]+)"', m.group(3)); view = re.search(r'view:\s*"([\w-]+)"', m.group(3))
            entries.append({"group": group, "id": m.group(1), "label": m.group(2), "hub": hub and hub.group(1),
                            "view": (view and view.group(1)) or m.group(1), "coming": "comingSoon" in m.group(3)})
        if re.match(r'^  \},?$', line) or re.search(r'type:\s*"standalone"', line):
            group = "(standalone)" if re.search(r'type:\s*"standalone"', line) else group
    for blk in re.findall(r'type:\s*"standalone",(.*?)\n\s*\},?\n', ns, re.S):
        g = lambda k: (re.search(k + r':\s*"([^"]+)"', blk) or [None, None])[1]
        if g("id") and not any(x.get("id") == g("id") for x in entries):
            entries.append({"group": "(standalone)", "id": g("id"), "label": g("label"), "hub": g("hub"),
                            "view": g("view") or g("id"), "coming": "comingSoon" in blk})
    return [e for e in entries if "id" in e], hubs


def view_components():
    txt = read(f"{SRC}/AppViewRouter.jsx")
    imports = {}
    for name, spec in re.findall(r'const (\w+) = lazy\(\(\) => import\("([^"]+)"\)\)', txt):
        imports[name] = spec
    for name, spec in re.findall(r'import (\w+) from "([^"]+)"', txt):
        imports.setdefault(name, spec)
    vmap = defaultdict(set)
    for vlist, comp in re.findall(r'\{\s*(activeView === "[\w-]+"(?:\s*\|\|\s*activeView === "[\w-]+")*|\[[^\]]+\]\.includes\(activeView\))\s*&&\s*\(?\s*<(\w+)', txt):
        for v in re.findall(r'"([\w-]+)"', vlist):
            vmap[v].add(comp)
    return {v: sorted(c) for v, c in vmap.items()}, imports


def main():
    os.makedirs(OUT, exist_ok=True)
    entries, hubs = nav()
    vmap, imports = view_components()
    views = []
    for e in entries:
        tabs = hubs.get(e["hub"], [{"view": e["view"], "label": e["label"], "roles": []}]) if e["hub"] else \
            [{"view": e["view"], "label": e["label"], "roles": []}]
        for t in tabs:
            views.append({"group": e["group"], "menu": e["label"], "menu_id": e["id"], "hub": e["hub"],
                          "view": t["view"], "tab_label": t["label"], "roles": t["roles"], "coming": e["coming"]})
    writers = defaultdict(set)
    for v in views:
        v["components"] = []
        for comp in vmap.get(v["view"], []):
            spec = imports.get(comp)
            f = spec and resolve(f"{SRC}/AppViewRouter.jsx", spec)
            if f:
                tree = scan(f, 0, set())
                v["components"].append(tree)

                def walk(n, path):
                    for w in n["writes"]:
                        writers[w].add(f'{v["menu"]} › {v["tab_label"]}')
                    for c in n["children"]:
                        walk(c, path)
                walk(tree, [])
    shared = {k: sorted(s) for k, s in writers.items() if len(s) > 1}
    with open(f"{OUT}/IA_INVENTORY.json", "w", encoding="utf8") as f:
        json.dump({"views": views, "shared_writes": shared}, f, ensure_ascii=False, indent=1)

    def count_tabs(n):
        return sum(len(t["tabs"]) for t in n["tabs"]) + sum(count_tabs(c) for c in n["children"])
    print("menu entries:", len(entries), "| hub/view entries:", len(views),
          "| unmapped views:", [v["view"] for v in views if not v["components"] and not v["coming"]])
    print("in-page tab/subtab items:", sum(count_tabs(c) for v in views for c in v["components"]))
    print("write endpoints used from >1 screen:", len(shared))


main()
