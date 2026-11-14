#!/usr/bin/env python3
"""INV-UI-12 — TAB MAKSIMAL 2 TINGKAT: tab/pil buatan sendiri HANYA BOLEH BERKURANG (ratchet, fase 3 · P1, L-01).

MASALAH YANG DICEGAH (audit UI tahap 2, L-01)
==============================================
Satu layar bisa punya bilah hub (pil hitam) → tab layar → pil/segmen → tombol-toggle, dengan EMPAT gaya berbeda.
Aturan fase 3 (§1.4): tingkat 1 = HubTabs (bilah hub), tingkat 2 = `components/PageTabs.jsx`; saringan =
`components/FilterChips.jsx` atau KNSelect, BUKAN tab; kebutuhan tingkat ke-3 → chip, seksi berjudul, atau pop-up.

Pola usang yang dihitung per berkas (komentar diabaikan):
  1. PIL HITAM — kelas aktif `bg-[#1C1C1E]` dipilih lewat ternary dengan `rounded-full` di className yang sama
     (gaya HubTabs lama & segmen buatan sendiri);
  2. TOMBOL-TOGGLE — `x ? "primary-button …" : "secondary-button …"` (tab dibuat dari tombol aksi);
  3. `TabBtn` buatan sendiri (definisi/pemakaian);
  4. `cfg-group-btn` (daftar grup Pusat Pengaturan sebagai tab vertikal).
Jumlah per berkas TIDAK BOLEH NAIK dari baseline; berkas BARU tidak boleh memakai pola itu. Turun = hijau.

MN-T1 (rencana 01 §5, standar L3) — dua pemeriksaan tambahan di berkas yang sama:
  INV-UI-13  Tiap hub di `config/hubTabs.js` paling banyak ENAM tab tampak (tanpa `hidden: true`; komentar diabaikan).
             Hub pada baseline `baselines/hub_tab_limit.json` tidak boleh melebihi angka baseline-nya.
  INV-UI-14  Komponen yang dirender `AppViewRouter.jsx` untuk view yang menjadi TAB HUB TAMPAK tidak boleh memuat
             `PageTabs` atau kelas `tab-bar` (tab tingkat ketiga). Berkas pada baseline `baselines/third_level_tabs.json`
             hanya boleh berkurang; berkas baru tidak boleh masuk. Kebutuhan tingkat ke-3 → FilterChips/seksi/pop-up.

Pakai:
    python scripts/guardrails/verify_page_tabs.py
    python scripts/guardrails/verify_page_tabs.py --self-test
    python scripts/guardrails/verify_page_tabs.py --update     # kencangkan baseline (hanya turun)
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import Guard, G, R, X  # noqa: E402
from _ratchet import (BASE_DIR, SRC, compare, iter_sources, load_baseline, strip_comments,  # noqa: E402
                      tightened, write_baseline)

NAME = "page_tabs"
STANDARD = {"components/PageTabs.jsx", "components/FilterChips.jsx", "components/HubTabs.jsx"}
PILL_ACTIVE = re.compile(r"\?\s*[\"'`][^\"'`]*?bg-\[#1C1C1E\]")
TOGGLE = re.compile(r"\?\s*[\"'`]primary-button[^\"'`]*[\"'`]\s*:\s*[\"'`]secondary-button")
TABBTN = re.compile(r"\bTabBtn\b")
CFG_GROUP = re.compile(r"(?<![\w-])cfg-group-btn(?![\w-])")
NOTE = ("Baseline ratchet INV-UI-12 (pil hitam · tombol-toggle primary/secondary · TabBtn · cfg-group-btn per berkas), "
        "dibuat fase 3 · P1 26 Okt 2026 sesudah HubTabs dibakukan. Hanya boleh TURUN; kencangkan dengan --update (P8).")


def count(text: str) -> int:
    code = strip_comments(text)
    pills = sum(1 for m in PILL_ACTIVE.finditer(code) if "rounded-full" in code[max(0, m.start() - 400):m.end() + 200])
    return pills + len(TOGGLE.findall(code)) + len(TABBTN.findall(code)) + len(CFG_GROUP.findall(code))


# ─── MN-T1 — INV-UI-13 (batas tab per hub) & INV-UI-14 (tanpa tab tingkat ketiga) ──────────────────────────────────
MAX_TABS = 6
HUBTABS_REL = "config/hubTabs.js"
ROUTER_REL = "AppViewRouter.jsx"
IMPORTS_REL = "appViewImports.js"
LIMIT_BASE = "hub_tab_limit"
THIRD_BASE = "third_level_tabs"
LIMIT_NOTE = ("Baseline INV-UI-13 (MN-T1): hub yang SUDAH melebihi enam tab tampak saat penjaga dibuat. Angka hanya boleh "
              "turun (--update); hub lain maks 6. Pesanan Pembelian 7 karena Landed Cost pindah dari Hutang (MN-T1).")
THIRD_NOTE = ("Baseline INV-UI-14 (MN-T1): berkas komponen tab hub tampak yang masih memuat PageTabs/kelas tab-bar (tab "
              "tingkat ketiga) sesudah MN-T1. Hanya boleh berkurang (--update); berkas baru tidak boleh masuk.")
HUB_RX = re.compile(r'^\s{2}"([\w-]+)":\s*\[(.*?)^\s{2}\],', re.S | re.M)
TAB_RX = re.compile(r'\{[^{}]*?\bview:\s*"([\w-]+)"[^{}]*\}')
THIRD_RX = re.compile(r"\bPageTabs\b|(?<![\w-])tab-bar(?![\w-])")


def hub_visible_tabs(hubtabs_src: str) -> dict:
    """hub → daftar view tab TAMPAK (tanpa `hidden: true`), dari `hubTabs.js` tanpa komentar."""
    code = strip_comments(hubtabs_src)
    out = {}
    for m in HUB_RX.finditer(code):
        out[m.group(1)] = [t.group(1) for t in TAB_RX.finditer(m.group(2))
                           if not re.search(r"\bhidden\s*:\s*true", t.group(0))]
    return out


def tab_limit_violations(hubs: dict, base: dict) -> list:
    out = []
    for hub, tabs in sorted(hubs.items()):
        limit = max(MAX_TABS, int(base.get(hub, 0)))
        if len(tabs) > limit:
            asal = f"baseline {base[hub]}" if hub in base else f"maks {MAX_TABS}"
            out.append(f"hub `{hub}` punya {len(tabs)} tab tampak ({asal}). Layar baru = tab di hub lain, atau satukan "
                       "dua layar (rencana 01 §5 butir 2).")
    return out


def router_components(router_src: str) -> dict:
    """view → nama komponen yang dirender `AppViewRouter.jsx` untuk view itu."""
    code = strip_comments(router_src)
    out = {}
    for m in re.finditer(r"\{([^{}]*?activeView[^{}]*?)&&\s*\(?\s*(?:<>\s*)?<([A-Z]\w*)", code, re.S):
        for v in re.findall(r'"([\w-]+)"', m.group(1)):
            out.setdefault(v, m.group(2))
    return out


def component_files(imports_src: str, router_src: str) -> dict:
    """nama komponen → path impor relatif `src` (lazy di appViewImports.js atau impor langsung di router)."""
    out = {n: p for n, p in re.findall(r'export const (\w+)\s*=\s*lazy\(\(\)\s*=>\s*import\("\./([^"]+)"\)\)', imports_src)}
    for n, p in re.findall(r'import\s+(\w+)\s+from\s+"\./([^"]+)"', router_src):
        out.setdefault(n, p)
    return out


def resolve_src(rel_noext: str):
    for cand in (rel_noext, rel_noext + ".jsx", rel_noext + ".js", rel_noext + "/index.jsx", rel_noext + "/index.js"):
        if (SRC / cand).is_file():
            return cand
    return None


def third_level_files(hubs: dict, router_src: str, imports_src: str, read=None) -> dict:
    """berkas komponen tab hub tampak yang memuat PageTabs/kelas tab-bar → daftar view yang merendernya."""
    if read is None:   # berkas nyata di frontend/src
        read, locate = (lambda rel: (SRC / rel).read_text(encoding="utf-8", errors="ignore")), resolve_src
    else:              # uji-diri: berkas tiruan ber-ekstensi .jsx
        locate = lambda rel: rel if rel.endswith((".js", ".jsx")) else rel + ".jsx"  # noqa: E731
    comps, files = router_components(router_src), component_files(imports_src, router_src)
    out = {}
    for view in sorted({v for tabs in hubs.values() for v in tabs}):
        rel = files.get(comps.get(view, ""))
        rel = locate(rel) if rel else None
        if rel and THIRD_RX.search(strip_comments(read(rel))):
            out.setdefault(rel, []).append(view)
    return out


def _load_json(name: str) -> dict:
    p = BASE_DIR / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _write_json(name: str, data: dict) -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def check_mnt1() -> tuple:
    """→ (kode keluar, pelanggaran INV-UI-13, pelanggaran INV-UI-14)."""
    hub_src = (SRC / HUBTABS_REL).read_text(encoding="utf-8")
    router_src = (SRC / ROUTER_REL).read_text(encoding="utf-8")
    imports_src = (SRC / IMPORTS_REL).read_text(encoding="utf-8")
    hubs = hub_visible_tabs(hub_src)
    limit_base = (_load_json(LIMIT_BASE).get("hubs") or {})
    third_base = set(_load_json(THIRD_BASE).get("files") or [])
    third = third_level_files(hubs, router_src, imports_src)
    if "--init-mnt1" in sys.argv:
        _write_json(LIMIT_BASE, {"_catatan": LIMIT_NOTE,
                                 "hubs": {h: len(t) for h, t in sorted(hubs.items()) if len(t) > MAX_TABS}})
        _write_json(THIRD_BASE, {"_catatan": THIRD_NOTE, "files": sorted(third)})
        print(f"baseline MN-T1 ditulis: {LIMIT_BASE}.json, {THIRD_BASE}.json ({len(third)} berkas)")
        return 0, 0, 0
    g13 = Guard("INV-UI-13", f"paling banyak {MAX_TABS} tab tampak per hub (baseline hanya boleh turun)")
    g13.bump(len(hubs))
    if not hubs:
        g13.add("HUB_TABS tidak terbaca dari config/hubTabs.js (format berubah?) — perbarui penjaga ini.")
    for v in tab_limit_violations(hubs, limit_base):
        g13.add(v)
    over = {h: len(t) for h, t in hubs.items() if len(t) > MAX_TABS}
    print(f"  hub > {MAX_TABS} tab: {over or '-'} (baseline {limit_base or '-'})")
    g14 = Guard("INV-UI-14", "tanpa tab tingkat ketiga — komponen tab hub tampak tanpa PageTabs/kelas tab-bar")
    g14.bump(len({v for t in hubs.values() for v in t}))
    for rel in sorted(set(third) - third_base):
        g14.add(f"{rel} (tab hub: {', '.join(third[rel])}) memuat PageTabs/kelas tab-bar — tab tingkat ketiga. Pakai "
                "components/FilterChips.jsx (saringan), seksi berjudul, atau pop-up; atau jadikan tab hub sendiri.")
    turun = sorted(third_base - set(third))
    print(f"  berkas tab tingkat ketiga: {len(third)} (baseline {len(third_base)})" + (f" · turun: {turun}" if turun else ""))
    if "--update" in sys.argv and not g13.violations and not g14.violations:
        _write_json(LIMIT_BASE, {"_catatan": LIMIT_NOTE, "hubs": {h: min(n, len(hubs.get(h, []))) for h, n in
                                                                  limit_base.items() if len(hubs.get(h, [])) > MAX_TABS}})
        _write_json(THIRD_BASE, {"_catatan": THIRD_NOTE, "files": sorted(third_base & set(third))})
        print("  baseline MN-T1 dikencangkan.")
    return g13.finish() | g14.finish(), len(g13.violations), len(g14.violations)


def current_counts() -> dict:
    out = {}
    for rel, text in iter_sources(lambda r: r in STANDARD):
        n = count(text)
        if n:
            out[rel] = n
    return out


def main() -> int:
    cur = current_counts()
    if "--init" in sys.argv:
        p = write_baseline(NAME, cur, NOTE)
        print(f"baseline ditulis: {p} ({len(cur)} berkas, {sum(cur.values())} pola)")
        return 0
    base = load_baseline(NAME)
    g = Guard("INV-UI-12", "tab maksimal 2 tingkat — tab/pil buatan sendiri hanya boleh berkurang")
    if not base:
        g.add("baseline scripts/guardrails/baselines/page_tabs.json tidak ada — jalankan dengan --init SEKALI.")
        return g.finish()
    g.bump(len(cur) + len(base))
    naik, baru, turun = compare(cur, base)
    for rel, n, b in naik:
        g.add(f"{rel} — tab/pil buatan sendiri NAIK {b} → {n}. Tingkat 2 = PageTabs; saringan = FilterChips/KNSelect.")
    for rel, n, _ in baru:
        g.add(f"{rel} — berkas BARU memakai tab/pil buatan sendiri ({n}×). Pakai components/PageTabs.jsx "
              "(tab) atau components/FilterChips.jsx (saringan).")
    print(f"  berkas berpola: {len(cur)} (baseline {len(base)}) · pola: {sum(cur.values())} (baseline {sum(base.values())})")
    if turun:
        print(f"  turun di {len(turun)} berkas (ratchet bisa dikencangkan dengan --update):")
        for rel, n, b in turun[:12]:
            print(f"    ↓ {rel}: {b} → {n}")
    if "--update" in sys.argv and not naik and not baru:
        p = write_baseline(NAME, tightened(cur, base), NOTE)
        print(f"  baseline dikencangkan: {p}")
    rc = g.finish()
    rc13_14, n13, n14 = check_mnt1()   # MN-T1 — INV-UI-13 & INV-UI-14
    total = len(g.violations) + n13 + n14
    # Satu baris ringkasan terakhir (dibaca alat penghitung penjaga): jumlah gabungan tiga invarian berkas ini.
    print(f"{G + '[PASS]' if not total else R + '[FAIL]'}{X} {total} pelanggaran total "
          f"(INV-UI-12 {len(g.violations)} · INV-UI-13 {n13} · INV-UI-14 {n14})")
    return rc | rc13_14


def self_test() -> int:
    gagal = 0

    def cek(nama, ok):
        nonlocal gagal
        print(f"  {'✓' if ok else '✗'} {nama}")
        gagal += 0 if ok else 1

    pill = ('<button className={`px-3 py-1 rounded-full border ${on ? "bg-[#1C1C1E] text-white" : "bg-white"}`}>A</button>')
    cek("pil hitam aktif (rounded-full + ternary) terhitung", count(pill) == 1)
    cek("bg-[#1C1C1E] tanpa ternary (tombol gelap biasa) tidak dihitung",
        count('<button className="rounded-full bg-[#1C1C1E] text-white">Bayar</button>') == 0)
    cek("tombol-toggle primary/secondary terhitung",
        count('<button className={tab === k ? "primary-button !py-1.5" : "secondary-button !py-1.5"} />') == 1)
    cek("primary-button biasa tidak dihitung", count('<button className="primary-button !py-1.5">Simpan</button>') == 0)
    cek("TabBtn & cfg-group-btn terhitung", count('const TabBtn = () => <button className="cfg-group-btn" />;\n<TabBtn />') == 3)
    cek("komentar tidak dihitung", count('// dulu TabBtn + "cfg-group-btn"\n/* rounded-full ? "bg-[#1C1C1E]" */') == 0)
    naik, baru, turun = compare({"a.jsx": 2, "n.jsx": 1}, {"a.jsx": 1, "b.jsx": 3})
    cek("naik + berkas baru → merah; turun dicatat", naik == [("a.jsx", 2, 1)] and baru == [("n.jsx", 1, 0)] and turun == [("b.jsx", 0, 3)])
    # MN-T1 — INV-UI-13
    def hubsrc(name, n, hidden=0, comment=0):
        tabs = "".join(f'    {{ view: "v{i}", label: "T{i}", roles: ["admin"] }},\n' for i in range(n))
        tabs += "".join(f'    {{ view: "h{i}", label: "H{i}", roles: ["admin"], hidden: true, aliasOf: "v0" }},\n' for i in range(hidden))
        tabs += "".join(f'    // {{ view: "c{i}", label: "C{i}", roles: ["admin"] }},\n' for i in range(comment))
        return f'export const HUB_TABS = {{\n  "{name}": [\n{tabs}  ],\n}};\n'
    cek("INV-UI-13: hub 6 tab (+ tersembunyi & komentar) → hijau",
        tab_limit_violations(hub_visible_tabs(hubsrc("x", 6, hidden=2, comment=3)), {}) == [])
    cek("INV-UI-13: hub 7 tab → merah", len(tab_limit_violations(hub_visible_tabs(hubsrc("x", 7)), {})) == 1)
    cek("INV-UI-13: hub baseline 8 → hijau", tab_limit_violations(hub_visible_tabs(hubsrc("pp", 8)), {"pp": 8}) == [])
    cek("INV-UI-13: hub baseline 8 menjadi 9 → merah",
        len(tab_limit_violations(hub_visible_tabs(hubsrc("pp", 9)), {"pp": 8})) == 1)
    # MN-T1 — INV-UI-14
    hubs = hub_visible_tabs('export const HUB_TABS = {\n  "h": [\n    { view: "a", label: "A", roles: ["admin"] },\n'
                            '    { view: "b", label: "B", roles: ["admin"], hidden: true, aliasOf: "a" },\n  ],\n};\n')
    router = ('{activeView === "a" && <AView x={1} />}\n{activeView === "b" && <BView />}\n'
              '{(activeView === "z" || activeView === "a2") && (\n  <ZView />\n)}\n')
    imports = ('export const AView = lazy(() => import("./features/x/AView"));\n'
               'export const BView = lazy(() => import("./features/x/BView"));\n')
    files = {"features/x/AView.jsx": 'import PageTabs from "../../components/PageTabs";\n<PageTabs tabs={[]} />',
             "features/x/BView.jsx": '<div className="tab-bar" />'}
    found = third_level_files(hubs, router, imports, read=lambda rel: files.get(rel, ""))
    cek("INV-UI-14: berkas baru ber-PageTabs di bawah tab hub tampak → terdeteksi (merah bila bukan baseline)",
        found == {"features/x/AView.jsx": ["a"]})
    cek("INV-UI-14: tab tersembunyi (alias) tidak dihitung; kelas tab-bar di komentar diabaikan",
        third_level_files(hubs, router, imports, read=lambda rel: "// tab-bar PageTabs") == {})
    cek("INV-UI-14: kondisi ganda `(a || b) && (<Comp` terbaca",
        router_components(router).get("a2") == "ZView" and router_components(router).get("b") == "BView")
    print(f"{G if not gagal else R}  SELF-TEST {'HIJAU' if not gagal else 'MERAH'} ({gagal} gagal){X}")
    return gagal


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(1 if self_test() else 0)
    raise SystemExit(main())
