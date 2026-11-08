"""Audit B1 (UI/UX WMS-RFID) — utilitas bersama sensus statis UI (HANYA BACA kode).

Dipakai oleh `b1_style_census.py` dan `b1_screen_matrix.py`. Tidak menulis apa pun ke repo;
keluaran mentah ditulis ke folder yang diberikan lewat `--out` (default: scratchpad audit).

Metode inti:
  * Berkas sumber = `frontend/src/**/*.{js,jsx}` KECUALI `__tests__/` dan `*.test.*`.
  * Komentar JS/JSX (`//…`, `/* … */`, `{/* … */}`) DIBUANG sebelum menghitung (diganti spasi,
    baris dipertahankan) supaya contoh di komentar tidak ikut terhitung. String TIDAK dibuang.
  * Area = `features/<x>` (folder tingkat-1 di bawah features), `components/ui`, `components`,
    atau folder tingkat-1 lain di `src` (`lib`, `hooks`, `utils`, …); berkas di akar src = `(root)`.
"""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# `B1_SRC=<folder src>` mengganti akar yang dipindai (mis. salinan `frontend/src` dari cabang main).
SRC = Path(os.environ["B1_SRC"]).resolve() if os.environ.get("B1_SRC") else ROOT / "frontend" / "src"
DEFAULT_OUT = Path(os.environ.get(
    "B1_OUT",
    r"C:/Users/abc/AppData/Local/Temp/claude/d999a0fd1df8a838/4f003146-8d75-4e0b-9783-daa1d8e525b4/scratchpad/audit-b1/static",
))

# Area gudang / kualitas / RFID / HP (dipakai untuk subtotal "area gudang").
WAREHOUSE_AREAS = {
    "features/wms", "features/inventory", "features/inspections", "features/rfid", "features/mobile",
}


def rel(p):
    return Path(p).resolve().relative_to(SRC).as_posix()


def is_test(relpath):
    return "__tests__/" in relpath or ".test." in relpath or relpath.startswith("setupTests")


def iter_sources(include_tests=False, exts=(".js", ".jsx")):
    for p in sorted(SRC.rglob("*")):
        if not p.is_file() or p.suffix not in exts:
            continue
        r = rel(p)
        if not include_tests and is_test(r):
            continue
        yield p, r


def area_of(relpath):
    parts = relpath.split("/")
    if parts[0] == "features":
        return "features/" + parts[1] if len(parts) > 2 else "features/(root)"
    if parts[0] == "components":
        if len(parts) > 2 and parts[1] == "ui":
            return "components/ui"
        return "components"
    if len(parts) == 1:
        return "(root)"
    return parts[0]


def strip_comments(text):
    """Buang komentar JS/JSX; string & template literal dipertahankan; baris dipertahankan.

    Heuristik: string '…'/"…" tidak boleh melintasi baris (aturan JS) — tanda kutip tunggal
    di teks JSX (mis. apostrof) paling jauh hanya "mengunci" satu baris.
    """
    out = []
    i, n = 0, len(text)
    state = "code"
    tpl_stack = []  # kedalaman kurawal saat masuk `${` dalam template
    brace = 0
    prev_sig = ""   # karakter non-spasi terakhir di mode code (untuk deteksi regex/komentar)
    while i < n:
        c = text[i]
        nx = text[i + 1] if i + 1 < n else ""
        if state == "code":
            if c == "/" and nx == "/" and prev_sig != "\\":
                # komentar baris (URL `://` ada di dalam string → tak sampai sini)
                j = text.find("\n", i)
                j = n if j == -1 else j
                out.append(" " * (j - i))
                i = j
                continue
            if c == "/" and nx == "*":
                j = text.find("*/", i + 2)
                j = n if j == -1 else j + 2
                seg = text[i:j]
                out.append(re.sub(r"[^\n]", " ", seg))
                i = j
                continue
            if c in "'\"":
                state = c
            elif c == "`":
                state = "tpl"
            elif c == "{":
                brace += 1
            elif c == "}":
                if tpl_stack and brace == tpl_stack[-1]:
                    tpl_stack.pop()
                    state = "tpl"
                else:
                    brace -= 1
            out.append(c)
            if not c.isspace():
                prev_sig = c
            i += 1
            continue
        if state in ("'", '"'):
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == state or c == "\n":
                state = "code"
            i += 1
            continue
        if state == "tpl":
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == "`":
                state = "code"
            elif c == "$" and nx == "{":
                out.append("{")
                i += 2
                tpl_stack.append(brace)
                state = "code"
                continue
            i += 1
            continue
    return "".join(out)


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def read_clean(path):
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    return raw, strip_comments(raw)


# ── JSX tag parsing ──────────────────────────────────────────────────────────

def tag_end(text, start):
    """Indeks setelah '>' penutup tag pembuka yang dimulai di `start` ('<'). Sadar {} dan kutip."""
    i, n = start + 1, len(text)
    depth = 0
    q = None
    while i < n:
        c = text[i]
        if q:
            if c == "\\":
                i += 2
                continue
            if c == q:
                q = None
            i += 1
            continue
        if c in "\"'`":
            if depth > 0 or c in "\"'":
                q = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == ">" and depth == 0:
            return i + 1
        i += 1
    return n


def attr_value(tag, name):
    """Nilai mentah atribut JSX `name` dalam teks tag (string literal atau ekspresi {…}); None bila tak ada."""
    m = re.search(r"(?<![\w-])" + re.escape(name) + r"\s*=\s*", tag)
    if not m:
        return None
    i = m.end()
    if i >= len(tag):
        return None
    c = tag[i]
    if c in "\"'":
        j = tag.find(c, i + 1)
        return tag[i:j + 1] if j != -1 else tag[i:]
    if c == "{":
        depth, j, q = 0, i, None
        while j < len(tag):
            ch = tag[j]
            if q:
                if ch == "\\":
                    j += 2
                    continue
                if ch == q:
                    q = None
            elif ch in "\"'`":
                q = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return tag[i:j + 1]
            j += 1
        return tag[i:]
    return None


STR_LIT = re.compile(r'"([^"\n]*)"|\'([^\'\n]*)\'|`([^`]*)`')


def class_tokens(value):
    """Token kelas dari nilai className (gabungan semua literal string di dalamnya)."""
    if value is None:
        return [], False
    if value[0] in "\"'":
        return value[1:-1].split(), True
    toks = []
    found = False
    for m in STR_LIT.finditer(value):
        s = m.group(1) if m.group(1) is not None else (m.group(2) if m.group(2) is not None else m.group(3))
        s = re.sub(r"\$\{[^}]*\}", " ", s or "")
        if s.strip():
            found = True
        toks.extend(s.split())
    return toks, found


def iter_tags(clean, tagname):
    """(pos, tag_text) untuk setiap tag pembuka `<tagname` (case-sensitive, batas kata)."""
    for m in re.finditer(r"<" + re.escape(tagname) + r"(?=[\s/>])", clean):
        end = tag_end(clean, m.start())
        yield m.start(), clean[m.start():end]


# ── Import graph ─────────────────────────────────────────────────────────────

IMPORT_RE = re.compile(r"""(?:import\s+(?:[^'"]*?\s+from\s+)?|import\(\s*|require\(\s*|export\s+[^'";]*?\s+from\s+)['"](\.{1,2}/[^'"]+)['"]""")


def resolve_import(from_rel, spec):
    base = (SRC / from_rel).parent
    target = (base / spec).resolve()
    cands = [target]
    for ext in (".jsx", ".js"):
        cands.append(Path(str(target) + ext))
    for ext in (".jsx", ".js"):
        cands.append(target / ("index" + ext))
    for c in cands:
        if c.is_file() and c.suffix in (".js", ".jsx"):
            try:
                return rel(c)
            except ValueError:
                return None
    return None


def imports_of(relpath, clean=None):
    if clean is None:
        _, clean = read_clean(SRC / relpath)
    out = []
    for m in IMPORT_RE.finditer(clean):
        r = resolve_import(relpath, m.group(1))
        if r:
            out.append(r)
    return out


# ── Layar dalam cakupan B1 ───────────────────────────────────────────────────
# view id → berkas akar (dari `AppViewRouter.jsx` + `appViewImports.js`). Entri tanpa view id
# (awalan `hp:`/`sales:`/`comp:`) = aplikasi HP & pemilih produk/stok penjualan. Banyak akar dipisah `|`.
SCREENS = [
    ("operations", "features/wms/OperationsView.jsx"),
    ("goods-receipts", "features/wms/grn/GoodsReceiptsView.jsx"),
    ("wms-outbound", "features/wms/OutboundView.jsx"),
    ("wms-cutting", "features/wms/CuttingOpsView.jsx"),
    ("repair-orders", "features/wms/repair/RepairOrdersView.jsx"),
    ("qc-inspection", "features/wms/QCInspection.jsx"),            # QcHubView initial="queue" → lazy QCInspection
    ("inspections", "features/inspections/InspectionsView.jsx"),   # QcHubView initial="docs" → lazy InspectionsView
    ("inventory-board", "features/inventory/InventoryStatusBoard.jsx"),
    ("stock-buckets", "features/inventory/StockBucketsView.jsx"),
    ("inventory-lots", "features/inventory/lots/LotsView.jsx"),
    ("wms-locations", "features/wms/LocationPutawayView.jsx"),
    ("md-warehouses", "features/wms/warehouses/WarehouseMasterView.jsx"),
    ("production", "features/production/ProductionView.jsx"),
    ("logistics", "features/logistics/LogisticsView.jsx"),
    ("cs-rfid-lokasi", "features/rfid/RfidLocationsView.jsx"),
    ("cs-rfid-tags", "features/rfid/RfidTagsView.jsx"),
    ("cs-rfid-gate", "features/rfid/RfidGateMonitorView.jsx"),
    ("escalations", "features/manager/EscalationManagement.jsx"),
    ("warehouse-admin-desk+my-desk", "features/desks/RoleDesk.jsx"),
    ("returns", "features/sales/SalesReturns.jsx"),
    ("interco-returns", "features/finance/interco/IntercoReturnsPanel.jsx|features/finance/interco/IntercoReturnInbox.jsx"),  # IntercoView only=[returns, return-inbox]
    ("purchase-returns", "features/purchasing/PurchaseReturns.jsx"),
    ("makloon-orders", "features/purchasing/MakloonOrdersView.jsx"),
    ("settings-receiving-ocr", "features/settings/ReceivingOcrSettings.jsx"),
    ("grade-master", "features/settings/masters/GradeMasterView.jsx"),
    ("settings-devices", "features/settings/devices/DevicesView.jsx|features/rfid/RfidDevicesView.jsx"),  # tab RFID
    ("settings-cfg-warehouse", "features/settings/cfg/SettingsGroupView.jsx|features/settings/config/SettingsHub.jsx"),  # mesin SettingsBrowser
    ("cs-stock-analytics", "features/inventory/StockAnalyticsView.jsx"),
    ("interco-transfers", "features/transfers/InterCompanyTransfers.jsx"),
    ("hp:MobileWarehouseApp", "features/mobile/MobileWarehouseApp.jsx"),
    ("hp:MobileOpsApp", "features/mobile/MobileOpsApp.jsx"),
    ("hp:MobileRegistration", "features/mobile/MobileRegistration.jsx"),
    ("hp:MobileShell", "features/mobile/MobileShell.jsx"),
    ("hp:MobileTaskActions", "features/mobile/MobileTaskActions.jsx"),
    ("sales:SalesPortal(katalog)", "features/sales/SalesPortal.jsx"),
    ("sales:MobileCatalog", "features/sales/mobile/MobileCatalog.jsx"),
    ("sales:MobileStockAtp", "features/sales/mobile/MobileStockAtp.jsx"),
    ("comp:ProductSelect", "components/ProductSelect.jsx"),
]


def routed_roots():
    """Berkas akar semua view lazy di appViewImports.js (batas penelusuran antar-layar)."""
    txt = (SRC / "appViewImports.js").read_text(encoding="utf-8")
    roots = set()
    for m in re.finditer(r'import\("\./([^"]+)"\)', txt):
        r = resolve_import("appViewImports.js", "./" + m.group(1))
        if r:
            roots.add(r)
    return roots


_IMP_CACHE = {}


def closure(root, stop=None, follow_prefix=("features/",), max_depth=99):
    """Penutupan impor relatif dari `root` ke berkas di bawah `follow_prefix`.

    Berhenti di akar view lain (`stop`) supaya layar lain tidak ikut. Mengembalikan
    {relpath: kedalaman}. `components/ProductSelect.jsx` (akar komponen) ikut bila root-nya.
    """
    stop = stop or set()
    roots = root.split("|") if isinstance(root, str) else list(root)
    seen = {r: 0 for r in roots}
    frontier = list(roots)
    while frontier:
        nxt = []
        for f in frontier:
            if f not in _IMP_CACHE:
                _IMP_CACHE[f] = imports_of(f)
            for t in _IMP_CACHE[f]:
                if t in seen or is_test(t):
                    continue
                if not t.startswith(follow_prefix):
                    continue
                if t in stop and t not in roots:
                    continue
                d = seen[f] + 1
                if d > max_depth:
                    continue
                seen[t] = d
                nxt.append(t)
        frontier = nxt
    return seen
