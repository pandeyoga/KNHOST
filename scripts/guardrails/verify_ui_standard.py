#!/usr/bin/env python3
"""G-UI-01/02/04/05/07 + K-B1-06 — STANDAR UI GUDANG v1: pola di luar standar HANYA BOLEH BERKURANG (ratchet).

MASALAH YANG DICEGAH (keluhan pemilik 9 Nov 2026: "standarisasi UI element mulai dari form, button size, adanya search,
filter dll dan ukurannya, design UI elementnya, harus ada export Excel"; audit B1 UI-26/27/28/30, B1b UI-52/53, B3b
EXP-01/02, B4 §3.14). Standar: `docs/KN_37_STANDAR_UI_GUDANG.md` (K-B4-01: ditegakkan ratchet, tanpa bongkar massal).

Metrik per berkas `frontend/src` (komentar dibuang; `__tests__/` & `components/ui/` dilewati):
  font_lt12     G-UI-01  ukuran huruf < 12 px: `text-[Npx]` & `fontSize: N` di JS/JSX + `font-size: Npx` di CSS
  hp_font_lt14  G-UI-01  aplikasi HP (`features/mobile/`): huruf < 14 px (`text-xs`, `text-[N<14px]`, `text-fs-12/13`) —
                         HP: info keputusan ≥ 16 px, pendukung ≥ 14 px; 12 px hanya metadata (B4 §3.2a, B1b UI-53)
  hex           G-UI-02  literal warna hex di JS/JSX (warna = token/kelas baku). Juga: himpunan hex BERBEDA seluruh
                         aplikasi tidak boleh bertambah (warna baru wajib lewat token `--kn-*` / kelas `kn-*`)
  btn_custom    G-UI-04  `<button>` bergaya Tailwind sendiri (tanpa kelas tombol baku / kelas CSS komponen)
  btn_force     K-B1-06  kelas tombol baku yang dipaksa ukurannya (`!py-*`, `!h-*`, `!text-*` … di string yang sama)
  hp_touch      G-UI-05  elemen interaktif di aplikasi HP (`features/mobile/`) tanpa tanda ukuran sentuh ≥ 48 px
                         (`btn-touch`, `kn-input-touch`, `kn-chip-touch`, `min-h-touch`, `py-4`, `py-3`+teks ≥ 16 px …)
  list_no_excel G-UI-07  `<PaginationBar>` tanpa `exportSpec` (tombol baku Unduh Excel/CSV lewat Pusat Export)
Aturan ratchet (`_ratchet.py`): jumlah per berkas NAIK → MERAH; berkas BARU dengan jumlah > 0 → MERAH; turun = hijau.

Tambahan KERAS (G-UI-07 · K-B4-07): setiap layar daftar WMS-RFID di `WMS_LISTS` (matriks B3b) WAJIB memasang
`<ExportMenu …>` atau `exportSpec` — pengecualian hanya di `WMS_LIST_EXEMPT` dengan alasan ≥ 20 karakter.

Pakai:
    python scripts/guardrails/verify_ui_standard.py                 # gate
    python scripts/guardrails/verify_ui_standard.py --census [--ref <git-ref>] [--json]   # sensus (sebelum/sesudah)
    python scripts/guardrails/verify_ui_standard.py --self-test
    python scripts/guardrails/verify_ui_standard.py --update        # kencangkan baseline (hanya turun)
    python scripts/guardrails/verify_ui_standard.py --init          # HANYA saat penjaga dibuat (FIX-4)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter
from typing import Dict, Iterable, List, Tuple

sys.path.insert(0, os.path.dirname(__file__))
from _common import ROOT, Guard, G, R, X  # noqa: E402
from _ratchet import (compare, iter_sources, load_baseline, strip_comments,  # noqa: E402
                      tightened, write_baseline, BASE_DIR, SRC)

METRICS = ("font_lt12", "hp_font_lt14", "hex", "btn_custom", "btn_force", "hp_touch", "list_no_excel")
NOTE = ("Baseline ratchet Standar UI Gudang v1 (FIX-4, 9 Nov 2026) — {m}. Angka = kondisi saat penjaga dibuat "
        "(sesudah perbaikan FIX-4). Hanya boleh TURUN; kencangkan dengan --update.")
STANDARD_FILES = {"components/PaginationBar.jsx", "components/ExportMenu.jsx"}

FONT_PX = re.compile(r"text-\[(\d+(?:\.\d+)?)px\]")
FONT_STYLE = re.compile(r"fontSize\s*:\s*[\"'`]?(\d+(?:\.\d+)?)(?:px)?[\"'`]?")
CSS_FONT = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)px")
HEX = re.compile(r"(?<![\w&])#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![\w-])")
STD_BTN = {"primary-button", "secondary-button", "ghost-button", "danger-button", "icon-button", "link-button",
           "tab-button", "nav-button", "btn-primary", "btn-secondary", "btn-danger"}
FORCE = re.compile(r"(?<![\w-])!(?:py|px|pt|pb|p|h|min-h|text)-[\w.\[\]#-]+")
TW_LIKE = re.compile(
    r"^(?:[a-z0-9-]+:)*-?(?:(?:p|px|py|pt|pb|pl|pr|ps|pe|m|mx|my|mt|mb|ml|mr|ms|me|gap|gap-x|gap-y|w|h|min-w|min-h|"
    r"max-w|max-h|size|top|left|right|bottom|inset|z)-(?:\d+(?:\.\d+)?|px|auto|full|screen|\[[^\]]+\])"
    r"|flex|flex-1|flex-wrap|grid|block|inline|inline-flex|inline-block|hidden|truncate|group|peer|relative|absolute|"
    r"fixed|sticky|sr-only|font-mono|font-sans|tabular-nums|text-(?:center|left|right)|active|disabled|underline|"
    r"uppercase|italic)$")
HP_DIR = "features/mobile/"
TOUCH_OK = {"btn-touch", "kn-input-touch", "field-touch", "kn-chip-touch", "min-h-touch", "min-h-touch-primary",
            "h-12", "h-14", "h-16", "min-h-12", "min-h-14", "py-4", "p-4", "py-3.5", "p-3.5", "py-5", "p-5",
            "m-tab", "m-act", "m-subpage-back", "m-back-float"}
TOUCH_MINH = re.compile(r"^min-h-\[(\d+)px\]$")
HP_SMALL = re.compile(r"(?<![\w-])(?:[a-z]+:)?text-(?:xs|fs-12|fs-13)(?![\w-])")
TEXT_BIG = {"text-[16px]", "text-[17px]", "text-[18px]", "text-[20px]", "text-base", "text-lg", "text-xl",
            "text-fs-16", "text-fs-20", "text-fs-24"}

#: G-UI-07 keras — layar daftar WMS-RFID (matriks B3b lampiran B) yang wajib punya tombol Unduh baku.
WMS_LISTS = (
    "features/wms/grn/GoodsReceiptsView.jsx", "features/wms/InboundScanInterface.jsx", "features/wms/QCInspection.jsx",
    "features/inspections/InspectionsView.jsx", "features/wms/LocationPutawayView.jsx",
    "features/wms/PutawayOrdersPanel.jsx", "features/wms/warehouses/WarehouseMasterView.jsx",
    "features/wms/TransferManagement.jsx", "features/inventory/CycleCount.jsx",
    "features/inventory/registration/InitialRegistration.jsx",
    "features/wms/InventoryStockView.jsx", "features/wms/repair/RepairOrdersView.jsx",
    "features/inventory/lots/LotsView.jsx", "features/wms/OutboundScanInterface.jsx", "features/wms/CuttingOpsView.jsx",
    "features/samples/CuttingDesk.jsx", "features/samples/SampleOrdersView.jsx", "features/logistics/LogisticsView.jsx",
    "features/logistics/HistoryPanel.jsx", "features/sales/SalesReturns.jsx", "features/purchasing/PurchaseReturns.jsx",
    "features/finance/interco/IntercoReturnsPanel.jsx", "features/purchasing/MakloonOrdersView.jsx",
    "features/manager/EscalationManagement.jsx", "features/rfid/RfidTagsView.jsx",
    "features/rfid/RfidPrintVerifyPanel.jsx", "features/rfid/RfidSecurityPanel.jsx",
    "features/rfid/RfidLocationsView.jsx", "features/rfid/CycleCountPanel.jsx", "features/wms/PutawayDraftsPanel.jsx",
    "features/wms/PendingCutsPanel.jsx", "features/logistics/FleetPanel.jsx", "features/rfid/RfidDevicesView.jsx",
    "features/rfid/GatePassageHistory.jsx", "features/rfid/RfidGateMonitorView.jsx", "features/rfid/GateReviewQueue.jsx",
    "features/rfid/U300PassageList.jsx",
)
#: Pengecualian beralasan (dinilai orang). Diperbarui saat layar memasang tombol Unduh.
WMS_LIST_EXEMPT: Dict[str, str] = {
    # Saldo (BalancesTable) diunduh dari induknya InventoryStockView (tombol di atas tabel saldo) — bukan di sini.
    "features/samples/CuttingDesk.jsx": "Meja Cutting = tiga antrean turunan dari tugas potong sample; daftar tugas yang "
                                        "sama diunduh di Cutting (CuttingOpsView, dataset wms_tasks).",
    "features/wms/PendingCutsPanel.jsx": "Antrean potong & roll anak = gabungan turunan /inventory/pending-cuts (bukan satu "
                                         "koleksi); roll anak diunduh dari Operasi Gudang › Stok › Roll.",
    "features/logistics/FleetPanel.jsx": "Master armada (fleet_vehicles) belum punya dataset; satu master kendaraan menunggu "
                                         "keputusan K-B3b-05 (vehicles vs fleet_vehicles) — sisa FIX-4.",
    "features/rfid/RfidGateMonitorView.jsx": "Berkas paket PREP-H (performa gate) yang belum digabung — tombol rfid_reads "
                                             "(dataset sudah siap) dipasang sesudah PREP-H masuk main; sisa FIX-4.",
    "features/rfid/GateReviewQueue.jsx": "Berkas PREP-H + hak lihat per kasus diperiksa per dokumen sumber (_case_access) — "
                                         "dataset rfid_v2_reviews butuh keputusan cakupan; sisa FIX-4.",
    "features/rfid/U300PassageList.jsx": "Berkas PREP-H; lintasan V2 (rfid_v2_*) belum dipetakan ke Pusat Export — sisa FIX-4.",
}


# ─────────────────────────────────────────────────────────────────────────────
def css_classes(css_texts: Iterable[str]) -> set:
    out = set()
    for txt in css_texts:
        txt = re.sub(r"/\*[\s\S]*?\*/", " ", txt)
        for m in re.finditer(r"\.([a-zA-Z_][\w-]*)", txt):
            out.add(m.group(1))
    return out


def iter_tags(code: str, tag: str):
    """→ (posisi, teks tag pembuka) untuk `<tag …>` — sadar kurung kurawal & kutip."""
    for m in re.finditer(r"<" + tag + r"(?=[\s/>])", code):
        i, n, depth, q = m.end(), len(code), 0, ""
        while i < n:
            c = code[i]
            if q:
                if c == "\\":
                    i += 2
                    continue
                if c == q:
                    q = ""
            elif c in "\"'`":
                q = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            elif c == ">" and depth == 0:
                break
            i += 1
        yield m.start(), code[m.start():i + 1]


def class_value(tag: str):
    """→ (tokens, literal?) dari atribut className, atau (None, False) bila tidak ada."""
    m = re.search(r"\bclassName\s*=\s*", tag)
    if not m:
        return None, False
    rest = tag[m.end():]
    if rest[:1] in "\"'":
        q = rest[0]
        end = rest.find(q, 1)
        return rest[1:end].split(), True
    if rest[:1] == "{":
        depth, i = 0, 0
        while i < len(rest):
            if rest[i] == "{":
                depth += 1
            elif rest[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        expr = rest[1:i]
        if re.match(r"\s*(?!cn\b|clsx\b|classNames\b|twMerge\b)[A-Za-z_]\w*\(", expr):
            return [], False          # fungsi pembentuk kelas proyek (mis. `pill(on)`) — argumen bukan kelas
        lits = re.findall(r"\"([^\"]*)\"|'([^']*)'|`([^`]*)`", expr)
        toks: List[str] = []
        for a, b, c in lits:
            toks += re.sub(r"\$\{[^}]*\}", " ", a or b or c).split()
        return toks, bool(toks)
    return None, False


def count_text(rel: str, text: str, css_defined: set) -> Dict[str, int]:
    out = dict.fromkeys(METRICS, 0)
    if rel.endswith(".css"):
        code = re.sub(r"/\*[\s\S]*?\*/", " ", text)
        out["font_lt12"] = sum(1 for v in CSS_FONT.findall(code) if float(v) < 12)
        return out
    code = strip_comments(text)
    out["font_lt12"] = sum(1 for v in FONT_PX.findall(code) if float(v) < 12) + \
        sum(1 for v in FONT_STYLE.findall(code) if float(v) < 12)
    out["hex"] = sum(1 for h in HEX.findall(code) if not h.isdigit())
    for _pos, tag in iter_tags(code, "button"):
        toks, lit = class_value(tag)
        if toks is None or not lit:
            continue
        if any(t in STD_BTN for t in toks):
            continue
        if any(t in css_defined and not TW_LIKE.match(t) for t in toks):
            continue
        out["btn_custom"] += 1
    for lit in re.findall(r"\"[^\"\n]*\"|'[^'\n]*'|`[^`]*`", code):
        toks = set(lit.strip("\"'`").split())
        if toks & STD_BTN:
            out["btn_force"] += len(FORCE.findall(lit))
    if rel.startswith(HP_DIR):
        out["hp_touch"] = hp_touch_count(code)
        out["hp_font_lt14"] = len(HP_SMALL.findall(code)) + sum(1 for v in FONT_PX.findall(code) if 12 <= float(v) < 14)
    if rel not in STANDARD_FILES:
        out["list_no_excel"] = sum(1 for _p, tag in iter_tags(code, "PaginationBar") if "exportSpec" not in tag)
    return out


def touch_ok(toks: List[str]) -> bool:
    s = set(toks)
    if s & TOUCH_OK:
        return True
    if any((m := TOUCH_MINH.match(t)) and int(m.group(1)) >= 48 for t in toks):
        return True
    return bool(s & {"py-3", "p-3"}) and bool(s & TEXT_BIG)


def hp_touch_count(code: str) -> int:
    n = 0
    for tag_name in ("button", "input", "select", "textarea"):
        for _pos, tag in iter_tags(code, tag_name):
            if tag_name == "input" and re.search(r"type\s*=\s*[\"'](?:checkbox|radio|hidden|file)[\"']", tag):
                continue
            toks, lit = class_value(tag)
            if toks is not None and not lit:
                continue                      # className dinamis murni — tidak bisa dinilai statis
            if not touch_ok(toks or []):
                n += 1
    return n


# ─────────────────────────────────────────────────────────────────────────────
def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                          errors="ignore", check=True).stdout


def sources(ref: str = "") -> Iterable[Tuple[str, str]]:
    """(rel dari frontend/src, teks) — dari pohon kerja atau dari `git <ref>`. JS/JSX + CSS."""
    skip = lambda r: "__tests__/" in r or r.startswith("components/ui/") or ".test." in r  # noqa: E731
    if not ref:
        yield from iter_sources(lambda r: ".test." in r)
        for p in sorted(SRC.rglob("*.css")):
            yield str(p.relative_to(SRC)).replace("\\", "/"), p.read_text(encoding="utf-8", errors="ignore")
        return
    for path in _git("ls-tree", "-r", "--name-only", ref, "frontend/src").splitlines():
        rel = path[len("frontend/src/"):]
        if not rel.endswith((".js", ".jsx", ".css")) or skip(rel):
            continue
        yield rel, _git("show", f"{ref}:{path}")


def collect(ref: str = "") -> Tuple[Dict[str, Dict[str, int]], Counter, Dict[str, str]]:
    files = list(sources(ref))
    css_defined = css_classes(t for r, t in files if r.endswith(".css"))
    per: Dict[str, Dict[str, int]] = {m: {} for m in METRICS}
    hexes: Counter = Counter()
    texts: Dict[str, str] = {}
    for rel, text in files:
        texts[rel] = text
        c = count_text(rel, text, css_defined)
        for m in METRICS:
            if c[m]:
                per[m][rel] = c[m]
        if not rel.endswith(".css"):
            for h in HEX.findall(strip_comments(text)):
                if not h.isdigit():
                    hexes[h.upper()] += 1
    return per, hexes, texts


def census(ref: str = "") -> Dict[str, object]:
    per, hexes, texts = collect(ref)
    area = lambda r: ("hp_gudang" if r.startswith(HP_DIR) else "gudang" if r.startswith(  # noqa: E731
        ("features/wms/", "features/rfid/", "features/inventory/", "features/inspections/")) else "lain")
    out: Dict[str, object] = {"ref": ref or "pohon kerja"}
    for m in METRICS:
        by_area = Counter()
        for rel, n in per[m].items():
            by_area[area(rel)] += n
        out[m] = {"total": sum(per[m].values()), "files": len(per[m]), **dict(by_area)}
    out["hex_distinct"] = len(hexes)
    wms_ok = [f for f in WMS_LISTS if f in texts and ("<ExportMenu" in texts[f] or "exportSpec" in texts[f])]
    out["wms_lists_with_export"] = f"{len(wms_ok)}/{len(WMS_LISTS)}"
    return out


CMPS = "eq|ne|in|gt|gte|lt|lte|contains|not_contains|starts|empty|not_empty"


def export_blocks(text: str) -> List[str]:
    """Teks `<ExportMenu …>` dan objek `exportSpec={{ … }}` (sadar kurung)."""
    code = strip_comments(text)
    out = [tag for _p, tag in iter_tags(code, "ExportMenu")]
    for m in re.finditer(r"exportSpec=\{\{", code):
        i, depth = m.end() - 2, 0
        while i < len(code):
            depth += code[i] == "{"
            depth -= code[i] == "}"
            if depth == 0:
                break
            i += 1
        out.append(code[m.start():i + 1])
    return out


def export_contract(texts: Dict[str, str], datasets: Dict[str, dict]) -> List[str]:
    """G-UI-07b — setiap tombol Unduh merujuk dataset yang ADA, kolom saringan/urut yang ADA & bisa disaring, basis
    tanggal yang ADA, dan cari hanya pada dataset yang punya jalur cari. Salah ketik → server 4xx saat diklik (senyap
    di uji layar), jadi dijaga statik."""
    bad: List[str] = []
    for rel, text in sorted(texts.items()):
        if rel.endswith(".css") or rel in STANDARD_FILES:
            continue
        for blk in export_blocks(text):
            m = re.search(r"\bdataset(?:=|:\s*)[\"']([\w]+)[\"']", blk)
            if not m:
                bad.append(f"{rel}: tombol Unduh tanpa dataset literal")
                continue
            ds = datasets.get(m.group(1))
            if not ds:
                bad.append(f"{rel}: dataset “{m.group(1)}” tidak ada di registry Pusat Export")
                continue
            cols = {c["key"] for c in ds["columns"] if c.get("filterable", True)}
            dates = {d["key"] for d in ds.get("date_fields") or []}
            for f in re.findall(r"\[\s*[\"']([\w.]+)[\"']\s*,\s*[\"'](?:" + CMPS + r")[\"']", blk):
                if f not in cols:
                    bad.append(f"{rel}: [{ds['id']}] kolom saringan “{f}” tidak ada/bukan kolom dasar")
            for k in re.findall(r"\bkey:\s*[\"']([\w.]+)[\"']", blk):
                if k not in cols:
                    bad.append(f"{rel}: [{ds['id']}] kolom urut “{k}” tidak ada")
            for f in re.findall(r"dateRange=\{\{\s*field:\s*[\"']([\w.]+)[\"']", blk):
                if f not in dates:
                    bad.append(f"{rel}: [{ds['id']}] basis tanggal “{f}” tidak ada")
            if re.search(r"\bsearch(?:=|:)", blk) and not any(
                    ds.get(k) for k in ("search_fields", "search_product_paths", "search_warehouse_paths",
                                        "search_entity_paths")):
                bad.append(f"{rel}: [{ds['id']}] memakai cari tetapi dataset tanpa jalur cari (search_fields)")
    return bad


def load_registry() -> Dict[str, dict]:
    sys.path.insert(0, str(ROOT / "backend"))
    from services.export_registry import DATASET_BY_ID  # noqa: E402 — registry murni (tanpa FastAPI/DB)
    return DATASET_BY_ID


def main() -> int:
    per, hexes, texts = collect()
    if "--init" in sys.argv:
        for m in METRICS:
            write_baseline(f"ui_{m}", per[m], NOTE.format(m=m))
        (BASE_DIR / "ui_hex_set.json").write_text(json.dumps(
            {"_catatan": "Himpunan warna hex berbeda di JS/JSX saat FIX-4 — warna BARU wajib lewat token --kn-*.",
             "total": len(hexes), "hex": sorted(hexes)}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("baseline ditulis:", ", ".join(f"ui_{m}" for m in METRICS), "+ ui_hex_set")
        return 0
    g = Guard("G-UI (Standar UI Gudang v1)", "pola di luar standar hanya boleh berkurang + daftar WMS-RFID wajib Unduh")
    naik_any = False
    for m in METRICS:
        base = load_baseline(f"ui_{m}")
        if not base and not (BASE_DIR / f"ui_{m}.json").exists():
            g.add(f"baseline ui_{m}.json tidak ada — jalankan --init SEKALI.")
            continue
        g.bump(len(per[m]) + len(base))
        naik, baru, turun = compare(per[m], base)
        naik_any = naik_any or bool(naik or baru)
        for rel, n, b in naik:
            g.add(f"[{m}] {rel} NAIK {b} → {n} — {HINT[m]}")
        for rel, n, _ in baru:
            g.add(f"[{m}] {rel} berkas BARU memakai pola usang ({n}×) — {HINT[m]}")
        print(f"  {m:<14} sekarang {sum(per[m].values()):>6} di {len(per[m]):>4} berkas · baseline "
              f"{sum(base.values()):>6}" + (f" · turun di {len(turun)} berkas" if turun else ""))
        if "--update" in sys.argv and not naik and not baru:
            write_baseline(f"ui_{m}", tightened(per[m], base), NOTE.format(m=m))
    hp = BASE_DIR / "ui_hex_set.json"
    if hp.exists():
        known = set(json.loads(hp.read_text(encoding="utf-8")).get("hex") or [])
        new = sorted(set(hexes) - known)
        g.bump()
        if new:
            g.add(f"[hex] {len(new)} warna hex BARU di aplikasi: {', '.join('#' + h for h in new[:12])} — "
                  "pakai token --kn-* / kelas kn-* (styles/tokens.css, tailwind `kn`).")
        print(f"  hex berbeda    sekarang {len(hexes)} · baseline {len(known)}")
    try:
        registry = load_registry()
    except Exception as exc:  # noqa: BLE001 — registry harus bisa diimpor tanpa server
        registry = None
        g.add(f"[G-UI-07b] registry Pusat Export tidak bisa diimpor: {exc}")
    if registry is not None:
        problems = export_contract(texts, registry)
        g.bump(sum(len(export_blocks(t)) for r, t in texts.items() if not r.endswith(".css")))
        for p in problems:
            g.add(f"[G-UI-07b] {p}")
        print(f"  kontrak Unduh  {sum(len(export_blocks(t)) for r, t in texts.items() if not r.endswith('.css'))} "
              f"tombol diperiksa · {len(problems)} masalah")
    for f in WMS_LISTS:
        g.bump()
        txt = texts.get(f)
        if txt is None:
            continue
        if "<ExportMenu" in txt or "exportSpec" in txt:
            continue
        why = (WMS_LIST_EXEMPT.get(f) or "").strip()
        if len(why) < 20:
            g.add(f"[G-UI-07] {f} — daftar WMS-RFID tanpa tombol Unduh baku (ExportMenu/exportSpec, K-B4-07).")
    if naik_any:
        print(f"{R}  → standar: docs/KN_37_STANDAR_UI_GUDANG.md{X}")
    return g.finish()


HINT = {
    "font_lt12": "huruf minimum 12 px (text-fs-12 … text-fs-24; HP info ≥ 16, pendukung ≥ 14).",
    "hp_font_lt14": "HP gudang: info keputusan text-fs-16, pendukung text-fs-14 (bukan text-xs / 12–13 px).",
    "hex": "warna lewat token/kelas baku (text-kn-*, bg-kn-*, var(--kn-*)), bukan hex lepas.",
    "btn_custom": "tombol pakai kelas baku primary/secondary/danger/ghost/icon-button (+ btn-sm/btn-touch).",
    "btn_force": "jangan paksa ukuran tombol baku dengan !py/!h/!text — pakai pengubah resmi btn-sm / btn-touch.",
    "hp_touch": "target sentuh HP ≥ 48 px: btn-touch / kn-input-touch / kn-chip-touch / min-h-touch.",
    "list_no_excel": "daftar berhalaman wajib Unduh Excel+CSV: PaginationBar exportSpec={{ dataset, … }}.",
}


def self_test() -> int:
    gagal = 0

    def cek(nama, ok):
        nonlocal gagal
        print(f"  {'✓' if ok else '✗'} {nama}")
        gagal += 0 if ok else 1

    css = {"m-card", "status-pill", "filter-chip"}
    c = count_text("features/x.jsx", '<span className="text-[11px] text-[#8E8E93]">a</span><p className="text-[12px]" />', css)
    cek("text-[11px] dihitung, text-[12px] tidak", c["font_lt12"] == 1)
    cek("hex di className dihitung", c["hex"] == 1)
    cek("komentar tidak dihitung", count_text("a.jsx", "// text-[9px] #FF0000\n/* #00FF00 */", css)["font_lt12"] == 0)
    cek("fontSize: 10 dihitung", count_text("a.jsx", "const s = { fontSize: 10 };", css)["font_lt12"] == 1)
    cek("CSS font-size 10.5px dihitung", count_text("a.css", ".x { font-size: 10.5px; } .y { font-size: 12px; }", css)["font_lt12"] == 1)
    cek("tombol Tailwind sendiri dihitung",
        count_text("a.jsx", '<button className="rounded px-2 py-1 bg-white">x</button>', css)["btn_custom"] == 1)
    cek("tombol baku tidak dihitung",
        count_text("a.jsx", '<button className="secondary-button btn-sm">x</button>', css)["btn_custom"] == 0)
    cek("tombol berkelas CSS komponen tidak dihitung",
        count_text("a.jsx", '<button className="filter-chip px-2">x</button>', css)["btn_custom"] == 0)
    cek("tombol className dinamis murni tidak dihitung",
        count_text("a.jsx", "<button className={cls}>x</button>", css)["btn_custom"] == 0)
    cek("fungsi pembentuk kelas proyek (pill(on)) dianggap dinamis, cn(...) tetap dibaca",
        count_text("a.jsx", '<button className={pill(x === "all")}>x</button>', css)["btn_custom"] == 0
        and count_text("a.jsx", '<button className={cn("px-2 py-1", a)}>x</button>', css)["btn_custom"] == 1)
    cek("!py-1 pada tombol baku dihitung",
        count_text("a.jsx", '<button className="primary-button !py-1 !h-8">x</button>', css)["btn_force"] == 2)
    cek("!py-1 tanpa kelas tombol baku tidak dihitung",
        count_text("a.jsx", '<div className="card !py-1" />', css)["btn_force"] == 0)
    hp = '<button className="secondary-button w-full py-2">Tutup</button><button className="primary-button btn-touch">Ok</button>' \
         '<input className="w-full p-3 text-[16px]" /><input type="checkbox" />'
    cek("HP: tombol py-2 dihitung, btn-touch & isian p-3+16px tidak", count_text("features/mobile/a.jsx", hp, css)["hp_touch"] == 1)
    cek("HP: text-xs & text-[13px] dihitung, text-sm tidak",
        count_text("features/mobile/a.jsx", '<p className="text-xs" /><b className="text-[13px]" /><i className="text-sm" />', css)["hp_font_lt14"] == 2)
    cek("hp_touch hanya di features/mobile", count_text("features/wms/a.jsx", hp, css)["hp_touch"] == 0)
    cek("PaginationBar tanpa exportSpec dihitung, dengan exportSpec tidak",
        count_text("a.jsx", "<PaginationBar page={1} exportConfig={{a: 1}} />\n<PaginationBar exportSpec={{ dataset: 'x' }} />", css)["list_no_excel"] == 1)
    reg = {"d": {"id": "d", "columns": [{"key": "status"}, {"key": "created_at"}], "date_fields": [{"key": "created_at"}],
                 "search_fields": ["number"]},
           "n": {"id": "n", "columns": [{"key": "status"}], "date_fields": []}}
    ok_src = '<ExportMenu dataset="d" filters={[["status", "eq", s]]} sort={[{ key: "created_at", dir: "desc" }]} search={q} />'
    cek("kontrak Unduh: dataset/kolom/urut/cari yang ada → bersih", export_contract({"a.jsx": ok_src}, reg) == [])
    cek("kontrak Unduh: kolom saringan salah ketik → merah",
        len(export_contract({"a.jsx": '<ExportMenu dataset="d" filters={[["statsu", "eq", s]]} />'}, reg)) == 1)
    cek("kontrak Unduh: dataset tak dikenal & cari tanpa jalur → merah",
        len(export_contract({"a.jsx": '<ExportMenu dataset="x" />', "b.jsx": '<ExportMenu dataset="n" search={q} />'}, reg)) == 2)
    cek("kontrak Unduh: exportSpec di PaginationBar ikut diperiksa",
        len(export_contract({"a.jsx": '<PaginationBar exportSpec={{ dataset: "d", sort: [{ key: "nope" }] }} />'}, reg)) == 1)
    naik, baru, turun = compare({"a.jsx": 2, "n.jsx": 1}, {"a.jsx": 1, "b.jsx": 3})
    cek("ratchet: naik + berkas baru merah, turun dicatat", naik == [("a.jsx", 2, 1)] and baru == [("n.jsx", 1, 0)] and turun == [("b.jsx", 0, 3)])
    print(f"{G if not gagal else R}  SELF-TEST {'HIJAU' if not gagal else 'MERAH'} ({gagal} gagal){X}")
    return gagal


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(1 if self_test() else 0)
    if "--census" in sys.argv:
        ref = sys.argv[sys.argv.index("--ref") + 1] if "--ref" in sys.argv else ""
        res = census(ref)
        print(json.dumps(res, ensure_ascii=False, indent=1))
        raise SystemExit(0)
    raise SystemExit(main())
