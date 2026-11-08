#!/usr/bin/env python3
"""Audit B1 — MATRIKS LAYAR × KOMPONEN BAKU / POLA NON-BAKU / KONTROL DAFTAR (HANYA BACA).

Untuk tiap layar di `b1_common.SCREENS`: berkas akar + penutupan impor relatif ke `features/**`
(berhenti di akar view lain dari `appViewImports.js`). Komentar dibuang sebelum dicocokkan.

Deteksi (semua = pola teks, bukan render — lihat kolom bukti `berkas:baris`):
  komponen baku   : pemakaian JSX `<Nama` (FormModal, FormSection, KNSelect, ProductSelect, FilterChips,
                    KNPager, PagedRows, PaginationBar, PageTabs, DetailModal, DetailDrawer, ResponsiveTable,
                    ErrorNotice, QtyDual, KNDatePicker) + ListControls = impor `components/ListControls`
                    atau `ListPageParts` (SearchBox/StatusTabs/ListToolbar/OptionTabs).
  non-baku        : `<select` mentah · `<table` mentah · `fixed inset-0` (modal buatan sendiri) ·
                    `window.confirm/alert/prompt` (+ `confirm(`/`alert(` telanjang) · `<input type="date|datetime-local|month"`.
  cari            : `<SearchBox` | `<TableFilterBar` | placeholder berisi "Cari" | `type="search"`.
  saring          : `<FilterChips` | `<StatusTabs` | `<OptionTabs` | `<LineFilter` | `useTableFilter` |
                    KNSelect/select yang testid/placeholder/ariaLabel/value-nya memuat filter|status|gudang|wh|site|entity|pt|jenis|kind|tipe|grade|lokasi.
  urut            : sortKey|sortBy|sortDir|setSort|onSort|sortable|sorts: | teks "Urutkan" | testid *sort*.
  halaman         : `<PaginationBar` | `<KNPager` | `<PagedRows` | "Tampilkan lagi|Muat lagi|Lihat semua|Tampilkan semua".
  batas server    : `limit: N` / `limit=N` / `page_size` (daftar dipotong server tanpa pager = risiko senyap).
  ekspor          : `exportConfig` | `downloadCsv|buildCsv|csvExport` | teks Ekspor/Unduh CSV/Excel/xlsx.
  saring gudang   : `useWarehouses` | state wh/warehouse filter | KNSelect/select ber-testid/placeholder gudang|wh|warehouse.
  saring PT       : `<EntitySwitcher` | state entityFilter/filterEntity | KNSelect/select ber-testid/placeholder entity|badan usaha|PT.
  ikut PT global  : berkas akar memakai prop `selectedEntity`/`entityId` (penyaring PT dari kepala aplikasi).
Juga: label id mentah (`|| x_id` / `{x.y_id}` sebagai teks) dan kandidat target sentuh < 44 px (perkiraan).

Keluaran: `<out>/screen_matrix.json`, `screen_matrix.csv`, `raw_id_labels.csv`, `touch_targets.csv`.
Usage:  PYTHONUTF8=1 python scripts/audit/b1_screen_matrix.py [--out DIR]
"""
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import b1_common as C  # noqa: E402

STD = ["FormModal", "FormSection", "KNSelect", "ProductSelect", "FilterChips", "KNPager", "PagedRows",
       "PaginationBar", "PageTabs", "DetailModal", "DetailDrawer", "ResponsiveTable", "ErrorNotice", "QtyDual",
       "KNDatePicker"]

NONSTD = {
    "select_mentah": re.compile(r"<select(?=[\s>])"),
    "table_mentah": re.compile(r"<table(?=[\s>])"),
    "modal_fixed_inset0": re.compile(r"fixed inset-0"),
    "window_confirm_alert_prompt": re.compile(r"\bwindow\.(?:confirm|alert|prompt)\s*\(|(?<![\w.])(?:confirm|alert|prompt)\s*\(\s*[`\"']"),
    "input_date_mentah": re.compile(r"<input[^>]*type=\"(?:date|datetime-local|month)\""),
}

FILTER_WORDS = r"(?:filter|saring|status|gudang|wh\b|whId|warehouse|site|entity|badan usaha|\bPT\b|jenis|kind|tipe|type|grade|lokasi|location|zone|zona|kategori|category)"
FEAT = {
    "cari": [re.compile(r"<SearchBox(?=[\s/>])"), re.compile(r"<TableFilterBar(?=[\s/>])"),
             re.compile(r"placeholder=[\"{`][^\"\n]*[Cc]ari"), re.compile(r"type=\"search\""),
             re.compile(r"\buseListSearch\("), re.compile(r"[sS]earchPlaceholder=")],
    "saring": [re.compile(r"<(?:FilterChips|StatusTabs|OptionTabs|LineFilter)(?=[\s/>])"), re.compile(r"useTableFilter\(")],
    "urut": [re.compile(r"\b(?:sortKey|sortBy|sortDir|setSort\w*|onSort|sortable|SortHeader)\b"), re.compile(r"\bsorts\s*:"),
             re.compile(r"Urutkan|[Uu]rut(?:an)? berdasarkan"), re.compile(r"data-testid=\"[^\"]*sort[^\"]*\"")],
    "halaman": [re.compile(r"<(?:PaginationBar|KNPager|PagedRows)(?=[\s/>])"),
                re.compile(r"\b(?:useListSearch|usePagedRows|usePagedList)\("),
                re.compile(r"Tampilkan lagi|Muat lagi|Muat lebih|Lihat semua|Tampilkan semua|Tampilkan \{")],
    "batas_server": [re.compile(r"\blimit\s*[:=]\s*\d+"), re.compile(r"[?&]limit=\d+"), re.compile(r"\bpage_size\b")],
    "ekspor": [re.compile(r"\bexportConfig\b"), re.compile(r"\b(?:downloadCsv|buildCsv)\b|csvExport"),
               re.compile(r"Ekspor|Unduh (?:CSV|Excel)|\.xlsx|text/csv")],
    "saring_gudang": [re.compile(r"\buseWarehouses\(|\b(?:whFilter|filterWh|warehouseFilter|filterWarehouse|setWhId|setWh|setWarehouseId|setWarehouseFilter|setWhFilter)\b"),
                      re.compile(r"<(?:KNSelect|select|SiteSelect)[^>]*(?:testid|placeholder|aria-label|ariaLabel)=[\"{`][^\"\n]*(?:gudang|Gudang|-wh|wh-|warehouse)")],
    "keadaan_kosong": [re.compile(r"empty-state|<EmptyState(?=[\s/>])|data-testid=\"[^\"]*-empty\"")],
    "error_coba_lagi": [re.compile(r"\bonRetry=")],
    "saring_PT": [re.compile(r"<EntitySwitcher(?=[\s/>])|\b(?:entityFilter|filterEntity|setEntityFilter|setFilterEntity|setEntityId|entFilter|setEnt|ownerFilter|setOwnerFilter)\b"),
                  re.compile(r"<(?:KNSelect|select)[^>]*(?:testid|placeholder|aria-label|ariaLabel)=[\"{`][^\"\n]*(?:entity|Entity|badan usaha|Badan usaha|Badan Usaha|\bPT\b|owner|pemilik)")],
}

# Berkas yang namanya menandakan isian (modal/form/wizard/editor) — dikecualikan dari deteksi saringan daftar.
FORMISH_FILE = re.compile(r"(?:Modal|Wizard|Form|Create|Editor|Dialog|Sheet|Section|Fields)\w*\.jsx?$")
FORM_VALUE = re.compile(r"\b(?:form|draft|f|p|gate|row|line|l|d|cfg|edit|e)\.\w+")

RAW_ID_FALLBACK =re.compile(r"(?:\|\||\?\?)\s*([\w.?\[\]]*?\b\w+_id)\s*(?=[}`)])")
RAW_ID_DIRECT = re.compile(r"(?<![=$\w])\{\s*([\w?]+(?:\??\.\w+)*\.\w+_id)\s*\}")

SMALL_TOK = re.compile(r"^(?:[a-z]+:)*!?(?:py-(?:0|0\.5|1|1\.5|px)|p-(?:0|0\.5|1|1\.5)|h-(?:4|5|6|7|8|9|10)|min-h-(?:0|6|7|8|9|10))$")
SMALL_TXT = re.compile(r"^(?:[a-z]+:)*!?text-\[(?:8|8\.5|9|9\.5|10|10\.5|11|11\.5)px\]$")
# Perkiraan tinggi kelas baku (padding + line-height 1.5 × font) — DUGAAN, bukan ukur peramban.
STD_HEIGHT = {"primary-button": 35.5, "secondary-button": 35.5, "danger-button": 33.5, "ghost-button": 32,
              "icon-button": 32, "link-button": 21, "tab-button": 35.5, "btn-primary": 33, "btn-secondary": 33,
              "btn-danger": 33, "btn-sm": 28, "btn-xs": 25, "field": 35.5, "nav-button": 31.5}


def est_height(toks):
    """Perkiraan kasar tinggi elemen dari utilitas Tailwind (px). None bila tak bisa diperkirakan."""
    h = None
    lh = None
    py = None
    for t in toks:
        b = re.sub(r"^(?:[a-z]+:)*!?", "", t)
        m = re.match(r"^h-(\d+(?:\.\d+)?)$", b)
        if m:
            h = float(m.group(1)) * 4
        m = re.match(r"^min-h-(\d+(?:\.\d+)?)$", b)
        if m:
            h = max(h or 0, float(m.group(1)) * 4)
        m = re.match(r"^min-h-\[(\d+)px\]$", b)
        if m:
            h = max(h or 0, float(m.group(1)))
        m = re.match(r"^py-(\d+(?:\.\d+)?)$", b) or re.match(r"^p-(\d+(?:\.\d+)?)$", b)
        if m:
            py = float(m.group(1)) * 4
        m = re.match(r"^text-\[(\d+(?:\.\d+)?)px\]$", b)
        if m:
            lh = float(m.group(1)) * 1.5
        lh = {"text-xs": 16, "text-sm": 20, "text-base": 24, "text-lg": 28}.get(b, lh)
    std = [STD_HEIGHT[t] for t in toks if t in STD_HEIGHT]
    if h is not None:
        return h
    if py is not None:
        return (lh or 21) + 2 * py + 2
    if std:
        return min(std)
    return None


def scan_screen(sid, root, stop):
    files = C.closure(root, stop)
    res = {"screen": sid, "root": root, "files": sorted(files), "n_files": len(files)}
    std = {k: {"n": 0, "root": 0, "ev": []} for k in STD + ["ListControls"]}
    non = {k: {"n": 0, "root": 0, "ev": []} for k in NONSTD}
    feat = {k: {"n": 0, "root": 0, "ev": []} for k in FEAT}
    for f in sorted(files):
        p = C.SRC / f
        if not p.exists():
            continue
        _, clean = C.read_clean(p)
        isroot = f in root.split("|")
        for name in STD:
            for m in re.finditer(r"<" + name + r"(?=[\s/>])", clean):
                std[name]["n"] += 1
                std[name]["root"] += int(isroot)
                if len(std[name]["ev"]) < 4:
                    std[name]["ev"].append(f"{f}:{C.line_of(clean, m.start())}")
        for m in re.finditer(r"from\s+['\"][./]+components/(?:ListControls|ListPageParts)['\"]", clean):
            std["ListControls"]["n"] += 1
            std["ListControls"]["root"] += int(isroot)
            std["ListControls"]["ev"].append(f"{f}:{C.line_of(clean, m.start())}")
        for k, rx in NONSTD.items():
            for m in rx.finditer(clean):
                non[k]["n"] += 1
                non[k]["root"] += int(isroot)
                if len(non[k]["ev"]) < 6:
                    non[k]["ev"].append(f"{f}:{C.line_of(clean, m.start())}")
        formish = bool(FORMISH_FILE.search(f.rsplit("/", 1)[-1]))
        for k, rxs in FEAT.items():
            if formish and k in ("saring", "saring_gudang", "saring_PT", "cari", "urut"):
                continue   # berkas modal/form/wizard: pilihan gudang/PT di sana = isian, bukan saringan daftar
            for rx in rxs:
                for m in rx.finditer(clean):
                    feat[k]["n"] += 1
                    feat[k]["root"] += int(isroot)
                    if len(feat[k]["ev"]) < 6:
                        feat[k]["ev"].append(f"{f}:{C.line_of(clean, m.start())} «{clean[m.start():m.start()+60].splitlines()[0]}»")
        # KNSelect/select sebagai saringan: lihat atribut tag
        for tagname in ("KNSelect", "select"):
            if formish:
                continue
            for pos, tag in C.iter_tags(clean, tagname):
                attrs = " ".join(filter(None, [C.attr_value(tag, a) for a in
                                              ("data-testid", "placeholder", "aria-label", "ariaLabel", "value")]))
                if re.search(FILTER_WORDS, attrs, re.I) and not re.search(FORM_VALUE, attrs):
                    feat["saring"]["n"] += 1
                    feat["saring"]["root"] += int(isroot)
                    if len(feat["saring"]["ev"]) < 6:
                        feat["saring"]["ev"].append(f"{f}:{C.line_of(clean, pos)} «<{tagname} {attrs[:50]}»")
    res["std"] = std
    res["nonstd"] = non
    res["feat"] = feat
    rootclean = " ".join(C.read_clean(C.SRC / r)[1] for r in root.split("|"))
    res["ikut_PT_global"] = bool(re.search(r"\b(?:selectedEntity|entityId)\b", rootclean))
    return res


def raw_ids(files):
    rows = []
    for f in sorted(files):
        p = C.SRC / f
        _, clean = C.read_clean(p)
        for rx, kind in ((RAW_ID_FALLBACK, "cadangan || x_id"), (RAW_ID_DIRECT, "tampil langsung {x.y_id}")):
            for m in rx.finditer(clean):
                ln = C.line_of(clean, m.start())
                line = clean.splitlines()[ln - 1].strip()
                # buang konteks non-tampilan: atribut key/value/testid/onClick, objek payload, URL
                pre = clean[max(0, m.start() - 40):m.start()]
                if re.search(r"(?:key|value|data-testid|id|href|to|onClick|onChange|selected|checked)=\{?[^{}]*$", pre):
                    continue
                if kind.startswith("cadangan") and re.search(r"\b\w+\s*:\s*[^,{}]*$", pre) and "${" not in pre and "<" not in pre:
                    # kemungkinan objek payload `{ x: a || b_id }`
                    continue
                if "axios" in line or "API}" in line or "params" in line:
                    continue
                rows.append({"file": f, "line": ln, "kind": kind, "expr": m.group(1), "src": line[:160]})
    return rows


def touch_targets(files):
    rows = []
    for f in sorted(files):
        _, clean = C.read_clean(C.SRC / f)
        for tagname in ("button", "input", "select", "a", "KNSelect", "label"):
            for pos, tag in C.iter_tags(clean, tagname):
                if tagname == "input" and re.search(r"type=\"(?:hidden|file)\"", tag):
                    continue
                if tagname == "label" and "onClick" not in tag and "htmlFor" not in tag:
                    continue
                if tagname == "a" and "onClick" not in tag and "href" not in tag:
                    continue
                val = C.attr_value(tag, "className")
                toks, _ = C.class_tokens(val)
                small = [t for t in toks if SMALL_TOK.match(t)]
                stxt = [t for t in toks if SMALL_TXT.match(t)]
                h = est_height(toks)
                if small or stxt or (h is not None and h < 44):
                    rows.append({"file": f, "line": C.line_of(clean, pos), "tag": tagname,
                                 "est_height_px": round(h, 1) if h is not None else "",
                                 "small_tokens": " ".join(small + stxt),
                                 "testid": (C.attr_value(tag, "data-testid") or "")[:60],
                                 "class_head": " ".join(toks)[:120]})
    return rows


def mark(cell):
    if cell["n"] == 0:
        return "✗"
    return f"✓{cell['n']}" if cell["root"] else f"c{cell['n']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(C.DEFAULT_OUT))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stop = C.routed_roots()
    screens = [scan_screen(sid, root, stop) for sid, root in C.SCREENS]
    (out / "screen_matrix.json").write_text(json.dumps(screens, ensure_ascii=False, indent=1), encoding="utf-8")
    cols = ["screen", "root", "n_files"] + STD + ["ListControls"] + list(NONSTD) + list(FEAT) + ["ikut_PT_global"]
    with open(out / "screen_matrix.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(cols)
        for s in screens:
            w.writerow([s["screen"], s["root"], s["n_files"]] + [mark(s["std"][k]) for k in STD + ["ListControls"]]
                       + [mark(s["nonstd"][k]) for k in NONSTD] + [mark(s["feat"][k]) for k in FEAT]
                       + [int(s["ikut_PT_global"])])
    scope = set()
    for s in screens:
        scope |= set(s["files"])
    rid = raw_ids(scope)
    with open(out / "raw_id_labels.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "line", "kind", "expr", "src"], lineterminator="\n")
        w.writeheader()
        w.writerows(rid)
    # target sentuh: aplikasi HP + layar yang dibuka penuh dari HP gudang (Kedatangan Barang) + MobileRegistration
    mob = {f for f in scope if f.startswith("features/mobile/")}
    for s in screens:
        if s["screen"] in ("hp:MobileWarehouseApp", "hp:MobileOpsApp", "hp:MobileRegistration", "hp:MobileShell",
                           "hp:MobileTaskActions", "goods-receipts"):
            mob |= set(s["files"])
    for p, r in C.iter_sources():
        if r.startswith("features/mobile/"):
            mob.add(r)
    tt = touch_targets(mob)
    with open(out / "touch_targets.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "line", "tag", "est_height_px", "small_tokens", "testid", "class_head"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(tt)
    print(f"layar={len(screens)} berkas_cakupan={len(scope)} label_id_mentah={len(rid)} kandidat_sentuh={len(tt)} "
          f"(dari {len(mob)} berkas HP/GRN)")
    print("ditulis ke", out)


if __name__ == "__main__":
    main()
