#!/usr/bin/env python3
"""Audit B1 — SENSUS GAYA statis per berkas & per area (HANYA BACA `frontend/src`).

Menghitung, per berkas `.js/.jsx` (tanpa `__tests__/` & `*.test.*`, komentar dibuang):
  * font arbitrer  : regex FONT_PX  `text-\\[(\\d+(?:\\.\\d+)?)px\\]` (ikut varian `sm:`/`hover:` dsb.)
                     + `text-[..rem|em]` terpisah; `fontSize:` di objek gaya.
  * warna hex      : regex HEX `(?<![\\w&])#([0-9a-fA-F]{8}|{6}|{4}|{3})(?![\\w-])` di seluruh teks
                     kode (className, style, konstanta). Konteks: `tw` = kelas arbitrer `-[#..]`,
                     `other` = string/gaya. Hex serba-angka (#101) dicatat terpisah (bisa nomor, bukan warna).
  * nilai arbitrer : `(p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|ml|mr|gap|gap-x|gap-y|space-x|space-y|h|w|
                     min-h|min-w|max-h|max-w|size|rounded*)-[..]`.
  * tombol         : tiap tag `<button` diurai (sadar {} & kutip), className-nya digolongkan:
                     baku_global (kelas sistem CSS: primary/secondary/ghost/danger/icon/link/tab/nav-button,
                     btn-primary/secondary/danger) · kelas_css_fitur (kelas lain yang punya aturan .css) ·
                     tailwind_sendiri (hanya utilitas) · dinamis (className={var} tanpa literal) · tanpa_class.
                     `<Button` (shadcn `components/ui/button`) dihitung terpisah.
Keluaran: `<out>/style_census_files.csv`, `style_census.json`, `buttons.csv`.

Usage:  PYTHONUTF8=1 python scripts/audit/b1_style_census.py [--out DIR]
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import b1_common as C  # noqa: E402

FONT_PX = re.compile(r"text-\[(\d+(?:\.\d+)?)px\]")
FONT_REM = re.compile(r"text-\[(\d*\.?\d+)(rem|em)\]")
FONT_SIZE_STYLE = re.compile(r"fontSize\s*:")
STYLE_FONT_INLINE = re.compile(r"style=\{\{[^}]*fontSize")
HEX = re.compile(r"(?<![\w&])#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![\w-])")
ARB = re.compile(
    r"(?<![\w\[-])(?:[a-z0-9]+:)*-?"
    r"(px|py|pt|pb|pl|pr|ps|pe|p|mx|my|mt|mb|ml|mr|m|gap-x|gap-y|gap|space-x|space-y|min-h|min-w|max-h|max-w|h|w|size|"
    r"rounded-(?:tl|tr|bl|br|t|r|b|l|s|e)|rounded)-\[([^\]\s]+)\]")

GLOBAL_BTN = {
    "primary-button", "secondary-button", "ghost-button", "danger-button", "icon-button", "link-button",
    "tab-button", "nav-button", "btn-primary", "btn-secondary", "btn-danger",
}
GLOBAL_PRIMARY4 = {"primary-button", "secondary-button", "ghost-button", "danger-button", "icon-button"}
# Utilitas mirip Tailwind yang KEBETULAN juga punya aturan di .css (mis. `.m-shell .px-3`) — bukan "kelas fitur".
TW_LIKE = re.compile(
    r"^(?:[a-z0-9-]+:)*-?(?:(?:p|px|py|pt|pb|pl|pr|ps|pe|m|mx|my|mt|mb|ml|mr|ms|me|gap|gap-x|gap-y|w|h|min-w|min-h|"
    r"max-w|max-h|size|top|left|right|bottom|inset|z)-(?:\d+(?:\.\d+)?|px|auto|full|screen|\[[^\]]+\])"
    r"|flex|flex-1|flex-wrap|grid|block|inline|inline-flex|inline-block|hidden|truncate|group|peer|relative|absolute|"
    r"fixed|sticky|sr-only|font-mono|font-sans|tabular-nums|text-(?:center|left|right)|active|disabled|underline|"
    r"uppercase|italic)$")
SIZE_TOK = re.compile(r"^(?:[a-z0-9]+:)*(py|p|h|min-h|pt|pb)-(\S+)$")
TEXT_TOK = re.compile(r"^(?:[a-z0-9]+:)*text-(xs|sm|base|lg|xl|2xl|\[[\d.]+px\])$")


def css_classes():
    defined = set()
    for p in C.SRC.rglob("*.css"):
        txt = p.read_text(encoding="utf-8", errors="replace")
        txt = re.sub(r"/\*[\s\S]*?\*/", " ", txt)
        for m in re.finditer(r"\.([a-zA-Z_][\w-]*)", txt):
            defined.add(m.group(1))
    return defined


def classify_button(tag, css_defined):
    val = C.attr_value(tag, "className")
    if val is None:
        return "tanpa_class", [], None
    toks, has_lit = C.class_tokens(val)
    if not has_lit:
        return "dinamis", toks, val
    if any(t in GLOBAL_BTN for t in toks):
        return "baku_global", toks, val
    feat = [t for t in toks if t in css_defined and t not in GLOBAL_BTN and not TW_LIKE.match(t)]
    if feat:
        return "kelas_css_fitur", toks, val
    return "tailwind_sendiri", toks, val


def scan_file(path, relpath, css_defined, btn_rows):
    raw, clean = C.read_clean(path)
    rec = {
        "file": relpath, "area": C.area_of(relpath), "lines": raw.count("\n") + 1,
    }
    fpx = [m.group(1) for m in FONT_PX.finditer(clean)]
    rec["font_px_n"] = len(fpx)
    rec["font_px_vals"] = dict(Counter(fpx))
    rec["font_rem_n"] = len(FONT_REM.findall(clean))
    rec["style_fontSize_n"] = len(FONT_SIZE_STYLE.findall(clean))
    rec["style_inline_fontSize_n"] = len(STYLE_FONT_INLINE.findall(clean))
    hexes, hex_tw, hex_digit = [], 0, 0
    for m in HEX.finditer(clean):
        v = m.group(1).lower()
        hexes.append(v)
        pre = clean[max(0, m.start() - 2):m.start()]
        if pre.endswith("[") or pre.endswith("-["):
            hex_tw += 1
        if v.isdigit():
            hex_digit += 1
    rec["hex_n"] = len(hexes)
    rec["hex_tw_n"] = hex_tw
    rec["hex_digitonly_n"] = hex_digit
    rec["hex_vals"] = dict(Counter(hexes))
    arb = Counter()
    for m in ARB.finditer(clean):
        prop = m.group(1)
        prop = "rounded" if prop.startswith("rounded") else prop
        arb[prop] += 1
    rec["arb_n"] = sum(arb.values())
    rec["arb_by_prop"] = dict(arb)
    # tombol
    cats = Counter()
    for pos, tag in C.iter_tags(clean, "button"):
        cat, toks, val = classify_button(tag, css_defined)
        cats[cat] += 1
        size = [t for t in toks if SIZE_TOK.match(t)]
        text = [t for t in toks if TEXT_TOK.match(t)]
        btn_rows.append({
            "file": relpath, "line": C.line_of(clean, pos), "area": rec["area"], "cat": cat,
            "size_tokens": " ".join(size), "text_tokens": " ".join(text),
            "has_hex_bg": int(bool(re.search(r"bg-\[#", " ".join(toks)))),
            "class_head": " ".join(toks)[:140],
        })
    rec["btn_total"] = sum(cats.values())
    for k in ("baku_global", "kelas_css_fitur", "tailwind_sendiri", "dinamis", "tanpa_class"):
        rec["btn_" + k] = cats.get(k, 0)
    rec["shadcn_Button_n"] = len(re.findall(r"<Button(?=[\s/>])", clean))
    # kemunculan kelas tombol baku di className APA PUN (bukan hanya <button>)
    occ = Counter()
    for m in re.finditer(r"(?<![\w-])(" + "|".join(sorted(GLOBAL_BTN, key=len, reverse=True)) + r")(?![\w-])", clean):
        occ[m.group(1)] += 1
    rec["global_btn_class_occ"] = sum(occ.values())
    rec["global_btn4_class_occ"] = sum(v for k, v in occ.items() if k in GLOBAL_PRIMARY4)
    rec["global_btn_class_by"] = dict(occ)
    return rec


def aggregate(recs):
    agg = {
        "files": len(recs), "lines": 0, "font_px_n": 0, "font_px_vals": Counter(), "font_rem_n": 0,
        "style_fontSize_n": 0, "style_inline_fontSize_n": 0, "hex_n": 0, "hex_tw_n": 0, "hex_digitonly_n": 0,
        "hex_vals": Counter(), "arb_n": 0, "arb_by_prop": Counter(), "btn_total": 0, "btn_baku_global": 0,
        "btn_kelas_css_fitur": 0, "btn_tailwind_sendiri": 0, "btn_dinamis": 0, "btn_tanpa_class": 0,
        "shadcn_Button_n": 0, "global_btn_class_occ": 0, "global_btn4_class_occ": 0,
    }
    for r in recs:
        for k, v in r.items():
            if k in ("file", "area", "global_btn_class_by"):
                continue
            if isinstance(v, dict):
                agg[k].update(v)
            else:
                agg[k] += v
    out = dict(agg)
    out["font_px_distinct"] = len(agg["font_px_vals"])
    out["font_px_vals"] = dict(sorted(agg["font_px_vals"].items(), key=lambda kv: float(kv[0])))
    out["hex_distinct"] = len(agg["hex_vals"])
    out["hex_distinct_non_digit"] = len([h for h in agg["hex_vals"] if not h.isdigit()])
    out["hex_vals_top30"] = agg["hex_vals"].most_common(30)
    del out["hex_vals"]
    out["arb_by_prop"] = dict(agg["arb_by_prop"].most_common())
    return out


def coordinator_variants(css_defined):
    """Cari regex yang mereproduksi angka koordinator (21 nilai · 8.903 pakai · 649 hex)."""
    res = {}
    allraw, allclean, alltest = [], [], []
    for p, r in C.iter_sources(include_tests=True, exts=(".js", ".jsx", ".ts", ".tsx")):
        raw = p.read_text(encoding="utf-8", errors="replace")
        (alltest if C.is_test(r) else allraw).append(raw)
        if not C.is_test(r):
            allclean.append(C.strip_comments(raw))
    css_txt = [p.read_text(encoding="utf-8", errors="replace") for p in C.SRC.rglob("*.css")]
    J = lambda xs: "\n".join(xs)  # noqa: E731
    variants = {
        "font_px[src non-test, komentar dibuang]": (FONT_PX, J(allclean)),
        "font_px[src non-test, mentah]": (FONT_PX, J(allraw)),
        "font_px[src + test, mentah]": (FONT_PX, J(allraw + alltest)),
        "font_any_arb text-\\[[^\\]]+\\] [src non-test, mentah]": (re.compile(r"text-\[([^\]]+)\]"), J(allraw)),
    }
    for name, (rx, txt) in variants.items():
        vals = rx.findall(txt)
        vals = [v if isinstance(v, str) else "".join(v) for v in vals]
        res[name] = {"uses": len(vals), "distinct": len(set(vals))}
    hexvars = {
        "hex HEX[src non-test, komentar dibuang]": (HEX, J(allclean)),
        "hex HEX[src non-test, mentah]": (HEX, J(allraw)),
        "hex HEX[src non-test + css]": (HEX, J(allraw + css_txt)),
        "hex #[0-9a-fA-F]{3,8}\\b [src non-test + css, case-sensitive]": (re.compile(r"#([0-9a-fA-F]{3,8})\b"), J(allraw + css_txt)),
        "hex #[0-9a-fA-F]{3,8}\\b [src non-test, case-sensitive]": (re.compile(r"#([0-9a-fA-F]{3,8})\b"), J(allraw)),
        "hex #[0-9a-fA-F]{6}|{3} [src+test+css, case-sensitive]": (re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b"), J(allraw + alltest + css_txt)),
        "hex hanya Tailwind -[#..] [src non-test]": (re.compile(r"-\[#([0-9a-fA-F]{3,8})\]"), J(allclean)),
    }
    for name, (rx, txt) in hexvars.items():
        vals = rx.findall(txt)
        res[name] = {"uses": len(vals), "distinct_case_sensitive": len(set(vals)),
                     "distinct_lower": len({v.lower() for v in vals})}
    # tombol: beberapa definisi "bergaya sendiri" vs "kelas baku"
    clean = J(allclean)
    res["occ kelas tombol baku (primary|secondary|ghost|danger|icon)-button di mana pun"] = len(re.findall(
        r"(?<![\w-])(?:primary|secondary|ghost|danger|icon)-button(?![\w-])", clean))
    res["occ kelas tombol baku + btn-(primary|secondary|danger) di mana pun"] = len(re.findall(
        r"(?<![\w-])(?:(?:primary|secondary|ghost|danger|icon)-button|btn-(?:primary|secondary|danger))(?![\w-])", clean))
    res["<button className=\"... bg-[#  (satu baris)"] = len(re.findall(r"<button[^>\n]*className=[\"{`][^>\n]*bg-\[#", clean))
    # grep satu-baris yang mereproduksi angka koordinator "390 tombol bergaya sendiri"
    res["grep1baris <button[^>]*className=\"[^\"]*(px-|py-)[^\"]*\""] = len(re.findall(
        r"<button[^>\n]*className=\"[^\"\n]*(?:px-|py-)[^\"\n]*\"", J(allraw)))
    res["grep1baris (primary|secondary|danger)-button (kemunculan)"] = len(re.findall(
        r"(?:primary|secondary|danger)-button", J(allraw)))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(C.DEFAULT_OUT))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    css_defined = css_classes()
    recs, btn_rows = [], []
    for p, r in C.iter_sources():
        recs.append(scan_file(p, r, css_defined, btn_rows))
    by_area = defaultdict(list)
    for r in recs:
        by_area[r["area"]].append(r)
    stop = C.routed_roots()
    scope_files = set()
    for sid, root in C.SCREENS:
        scope_files |= set(C.closure(root, stop))
    summary = {
        "total_src": aggregate(recs),
        "area_gudang(wms+inventory+inspections+rfid+mobile)": aggregate(
            [r for r in recs if r["area"] in C.WAREHOUSE_AREAS]),
        "cakupan_layar_B1(closure)": aggregate([r for r in recs if r["file"] in scope_files]),
        "per_area": {k: aggregate(v) for k, v in sorted(by_area.items())},
        "coordinator_variants": coordinator_variants(css_defined),
        "scope_files": sorted(scope_files),
    }
    (out / "style_census.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    cols = ["file", "area", "lines", "font_px_n", "font_px_distinct", "font_rem_n", "style_fontSize_n",
            "hex_n", "hex_distinct", "hex_tw_n", "hex_digitonly_n", "arb_n", "btn_total", "btn_baku_global",
            "btn_kelas_css_fitur", "btn_tailwind_sendiri", "btn_dinamis", "btn_tanpa_class", "shadcn_Button_n",
            "global_btn_class_occ", "in_scope", "font_px_vals"]
    with open(out / "style_census_files.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in recs:
            row = dict(r)
            row["font_px_distinct"] = len(r["font_px_vals"])
            row["hex_distinct"] = len(r["hex_vals"])
            row["in_scope"] = int(r["file"] in scope_files)
            row["font_px_vals"] = " ".join(f"{k}:{v}" for k, v in sorted(r["font_px_vals"].items(), key=lambda kv: float(kv[0])))
            w.writerow(row)
    with open(out / "buttons.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(btn_rows[0].keys()) + ["in_scope"], lineterminator="\n")
        w.writeheader()
        for b in btn_rows:
            b = dict(b)
            b["in_scope"] = int(b["file"] in scope_files)
            w.writerow(b)
    t = summary["total_src"]
    print(f"files={t['files']} font_px uses={t['font_px_n']} distinct={t['font_px_distinct']} "
          f"hex uses={t['hex_n']} distinct={t['hex_distinct']} arb={t['arb_n']} buttons={t['btn_total']}")
    print("ditulis ke", out)


if __name__ == "__main__":
    main()
