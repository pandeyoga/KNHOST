"""Komponen halaman (HTML) untuk Panduan UAT — A4 lanskap, dicetak lewat Chrome headless."""
from html import escape

DOC_ID = "KN-UAT-E2E-002"
VERSION = "2.0"
DATE = "21 Oktober 2026"

CSS = r"""
@page { size: A4 landscape; margin: 11mm 10mm 12mm 10mm;
  @bottom-left { content: "ERP Kain Nusantara · Panduan UAT End-to-End v2.0 · KN-UAT-E2E-002"; font: 7pt 'Segoe UI', Arial; color:#64748B; }
  @bottom-right { content: "Hal. " counter(page) " / " counter(pages); font: 7pt 'Segoe UI', Arial; color:#64748B; } }
@page cover { margin: 0; @bottom-left { content: none } @bottom-right { content: none } }
* { box-sizing: border-box; }
html, body { margin:0; padding:0; background:#FFFFFF; color:#0F172A; font-family:'Segoe UI', Arial, sans-serif; font-size:8.6pt; line-height:1.32; }
:root { --ink:#0F172A; --muted:#475569; --line:#E2E8F0; --soft:#F8FAFC; --blue:#1D4ED8; --amber:#B45309; --red:#B91C1C; --green:#15803D; }
.sec { break-before: page; }
.sec:first-of-type { break-before: auto; }
h1 { font-size:20pt; margin:0 0 2mm 0; letter-spacing:-.2px; }
h2 { font-size:13.5pt; margin:0; letter-spacing:-.1px; }
h3 { font-size:10pt; margin:3mm 0 1.5mm 0; }
p { margin: 0 0 1.6mm 0; }
.kicker { font-size:7.4pt; font-weight:700; letter-spacing:.9px; text-transform:uppercase; color:#475569; }
.head { display:flex; justify-content:space-between; align-items:flex-end; border-bottom:2px solid #0F172A; padding-bottom:1.6mm; margin-bottom:2.4mm; }
.head .right { text-align:right; font-size:7.6pt; color:#334155; max-width:120mm; }
.chips { display:flex; flex-wrap:wrap; gap:1.4mm; justify-content:flex-end; margin-top:1mm; }
.chip { display:inline-block; border:1px solid #CBD5E1; border-radius:10px; padding:.3mm 2.2mm; font-size:7.2pt; color:#0F172A; background:#F8FAFC; white-space:nowrap; }
.chip.r { border-color:#FCA5A5; background:#FEF2F2; color:#991B1B; }
.chip.g { border-color:#86EFAC; background:#F0FDF4; color:#166534; }
.chip.a { border-color:#FCD34D; background:#FFFBEB; color:#92400E; }
.lead { font-size:8.4pt; color:#334155; margin-bottom:2mm; }
.flow { display:block; width:100%; height:auto; border:1px solid #E2E8F0; border-radius:4px; }
.strip { display:grid; grid-template-columns: repeat(4, 1fr); gap:2mm; margin:2.2mm 0 2.2mm 0; }
.strip.c3 { grid-template-columns: repeat(3, 1fr); }
.strip.c4 { grid-template-columns: repeat(4, 1fr); }
.strip.c2 { grid-template-columns: repeat(2, 1fr); }
.box { border:1px solid #E2E8F0; border-left:3px solid #1D4ED8; border-radius:4px; padding:1.6mm 2.2mm; background:#FFFFFF; font-size:7.8pt; }
.box b.t { display:block; font-size:7.4pt; letter-spacing:.6px; text-transform:uppercase; color:#1E3A8A; margin-bottom:.6mm; }
.box.a { border-left-color:#B45309; } .box.a b.t { color:#92400E; }
.box.r { border-left-color:#B91C1C; background:#FFFBFB; } .box.r b.t { color:#991B1B; }
.box.g { border-left-color:#15803D; } .box.g b.t { color:#166534; }
.box ul { margin:0; padding-left:3.6mm; } .box li { margin:0 0 .3mm 0; }
table { width:100%; border-collapse:collapse; }
table.steps { font-size:7.55pt; table-layout:fixed; }
table.steps thead { display: table-header-group; }
table.steps th { background:#0F172A; color:#FFFFFF; font-weight:600; text-align:left; padding:1.1mm 1.4mm; font-size:7.2pt; letter-spacing:.2px; }
table.steps td { border-bottom:1px solid #E2E8F0; padding:1.05mm 1.4mm; vertical-align:top; }
table.steps tr { break-inside: avoid; }
table.steps tr:nth-child(even) td { background:#F8FAFC; }
td.no { font-weight:700; white-space:nowrap; }
.role { display:inline-block; padding:0 1.4mm; border-radius:3px; color:#FFFFFF; font-weight:600; font-size:7pt; margin-bottom:.4mm; }
.acct { color:#475569; font-size:6.6pt; display:block; word-break:break-all; }
.nav { font-family: Consolas, 'Cascadia Mono', monospace; font-size:7pt; color:#1E293B; background:#EEF2FF; padding:0 .8mm; border-radius:2px; line-height:1.45; overflow-wrap:anywhere; }
.btn { display:inline-block; border:1px solid #94A3B8; border-radius:3px; padding:0 1.1mm; font-size:6.9pt; font-weight:600; background:#FFFFFF; line-height:1.35; }
.dec { color:#92400E; }
.dec b { color:#78350F; }
.t-ok { color:#166534; font-weight:600; } .t-bad { color:#991B1B; font-weight:700; } .t-na { color:#64748B; } .t-warn { color:#92400E; font-weight:600; }
table.grid { font-size:7.6pt; table-layout:fixed; }
table.grid th { background:#E2E8F0; text-align:left; padding:1mm 1.4mm; font-size:7.2pt; }
table.grid td { border-bottom:1px solid #E2E8F0; padding:1mm 1.4mm; vertical-align:top; }
table.grid tr { break-inside: avoid; }
.sched td { padding:1.2mm 1.4mm; }
.sched td.time { font-weight:700; white-space:nowrap; }
.sched tr.brk td { background:#F1F5F9; color:#475569; font-style:italic; }
.sched ol { margin:0; padding-left:3.6mm; } .sched li { margin:0 0 .25mm 0; }
.pill { display:inline-block; border-radius:8px; padding:0 1.6mm; font-size:6.9pt; font-weight:700; color:#FFFFFF; background:#0F172A; }
.cover { page: cover; width:297mm; height:210mm; position:relative; overflow:hidden; background:#0F172A; color:#FFFFFF; padding:18mm 20mm; }
.cover h1 { font-size:30pt; line-height:1.1; margin:4mm 0 3mm 0; }
.cover .sub { font-size:12pt; color:#CBD5E1; max-width:150mm; }
.cover .meta { position:absolute; left:20mm; bottom:16mm; right:20mm; display:grid; grid-template-columns: repeat(4, 1fr); gap:5mm; font-size:8.2pt; color:#E2E8F0; }
.cover .meta .lbl { display:block; color:#FFFFFF; font-size:7pt; letter-spacing:.8px; text-transform:uppercase; margin-bottom:1mm; opacity:.75; }
.cover .band { position:absolute; right:-30mm; top:-20mm; width:150mm; height:150mm; border-radius:50%; background: radial-gradient(circle at 30% 30%, #1D4ED8 0%, rgba(29,78,216,0) 70%); opacity:.55; }
.cover .lanes { position:absolute; right:18mm; top:34mm; width:88mm; }
.cover .lanes div { height:7mm; margin-bottom:2mm; border-radius:2mm; display:flex; align-items:center; padding-left:3mm; font-size:7.6pt; font-weight:600; }
.toc { columns: 2; column-gap: 10mm; font-size:8.4pt; }
.toc div { break-inside: avoid; padding:.9mm 0; border-bottom:1px dotted #CBD5E1; display:flex; justify-content:space-between; }
.toc div span:first-child b { display:inline-block; min-width:12mm; }
.sev { display:inline-block; min-width:9mm; text-align:center; border-radius:3px; padding:0 1mm; font-weight:700; font-size:6.9pt; color:#FFFFFF; }
.sev.P1 { background:#B91C1C; } .sev.P2 { background:#D97706; } .sev.P3 { background:#64748B; } .sev.OK { background:#15803D; }
.sign { display:grid; grid-template-columns: repeat(4, 1fr); gap:6mm; margin-top:6mm; }
.sign div { border-top:1px solid #0F172A; padding-top:1mm; font-size:7.6pt; height:22mm; }
.small { font-size:7.2pt; color:#475569; }
.cb { display:inline-block; width:2.8mm; height:2.8mm; border:1px solid #475569; border-radius:.5mm; vertical-align:-.4mm; margin-right:.6mm; }
.nobreak { break-inside: avoid; }
"""

ROLE_COLORS = {
    "Pelanggan": "#64748B", "Sales": "#2563EB", "Admin Sales": "#4F46E5", "Manajer": "#D97706", "PIC": "#D97706",
    "Finance": "#059669", "Gudang": "#0D9488", "Admin Gudang": "#0E7490", "Sopir": "#0891B2", "Ekspedisi": "#0891B2",
    "QC": "#9333EA", "MD Quality": "#7C3AED", "MD": "#DB2777", "R&D": "#DB2777", "Desainer": "#E11D48",
    "Pembelian": "#EA580C", "Supplier": "#78716C", "Mitra": "#78716C", "Admin Sample": "#C026D3", "CST": "#A16207",
    "Sistem": "#475569", "Fasilitator": "#0F172A", "Admin": "#0F172A", "Semua": "#0F172A",
}

ACCOUNTS = {
    "Sales": "sales@kainnusantara.id", "Admin Sales": "salesadmin@kainnusantara.id",
    "Manajer": "manager@kainnusantara.id", "PIC": "manager@kainnusantara.id", "Finance": "finance@kainnusantara.id",
    "Gudang": "warehouse@kainnusantara.id", "Admin Gudang": "wh.admin@kainnusantara.id",
    "Sopir": "driver@kainnusantara.id", "QC": "qc@kainnusantara.id", "MD Quality": "mdquality@kainnusantara.id",
    "MD": "md@kainnusantara.id", "R&D": "md@kainnusantara.id", "Desainer": "designer@kainnusantara.id",
    "Pembelian": "manager@kainnusantara.id", "Admin Sample": "sampleadmin@kainnusantara.id",
    "CST": "salesadmin.cst@kainnusantara.id", "Admin": "admin@kainnusantara.id",
}


def role_cell(role, acct=None):
    color = ROLE_COLORS.get(role.split(" ·")[0].split(" (")[0], "#334155")
    a = acct if acct is not None else ACCOUNTS.get(role.split(" ·")[0].split(" (")[0], "")
    return f'<span class="role" style="background:{color}">{escape(role)}</span>' + (f'<span class="acct">{escape(a)}</span>' if a else "")


def fmt(s):
    """Markup ringan: `nav`  [Tombol]  **tebal**  ->  —"""
    import re
    s = escape(s)
    s = re.sub(r"`([^`]+)`", r'<span class="nav">\1</span>', s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r'<span class="btn">\1</span>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*([^*\n]+?)\*(?![\w*])", r"<i>\1</i>", s)
    s = s.replace("-&gt;", "→")
    s = s.replace("\n", "<br>")
    return s


def test_cell(t):
    if not t:
        return '<span class="t-na">○ belum diuji</span>'
    k, _, rest = t.partition(" ")
    cls = {"OK": "t-ok", "BUG": "t-bad", "GAP": "t-warn", "NA": "t-na", "INFO": "t-na"}.get(k, "t-na")
    sym = {"OK": "✓", "BUG": "✗", "GAP": "!", "NA": "○", "INFO": "i"}.get(k, "")
    return f'<span class="{cls}">{sym} {fmt(rest)}</span>'


def steps_table(rows, widths=(6, 11, 15, 22, 15, 21, 10)):
    cols = ["No", "Peran · akun", "Navigasi (menu › tab › tombol)", "Aktivitas & input pengguna",
            "Keputusan / cabang", "Hasil yang harus terlihat", "Uji pra-UAT"]
    h = "".join(f'<col style="width:{w}%">' for w in widths)
    out = [f'<table class="steps"><colgroup>{h}</colgroup><thead><tr>' + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead><tbody>"]
    for r in rows:
        no, role, nav, act, dec, exp, test = (list(r) + [""] * 7)[:7]
        acct = None
        if isinstance(role, tuple):
            role, acct = role
        out.append("<tr>" + f'<td class="no">{escape(no)}</td>' + f"<td>{role_cell(role, acct)}</td>" +
                   f"<td>{fmt(nav)}</td><td>{fmt(act)}</td><td class=\"dec\">{fmt(dec)}</td><td>{fmt(exp)}</td>"
                   f"<td>{test_cell(test)}</td></tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def boxes(items, cols=4):
    cls = {4: "", 3: " c3", 2: " c2"}[cols]
    out = [f'<div class="strip{cls}">']
    for kind, title, lines in items:
        lis = "".join(f"<li>{fmt(x)}</li>" for x in lines)
        out.append(f'<div class="box {kind}"><b class="t">{escape(title)}</b><ul>{lis}</ul></div>')
    out.append("</div>")
    return "".join(out)


def head(kicker, title, chips=(), right=""):
    ch = "".join(f'<span class="chip {c[0]}">{escape(c[1])}</span>' if isinstance(c, tuple) else f'<span class="chip">{escape(c)}</span>' for c in chips)
    return (f'<div class="head"><div><div class="kicker">{escape(kicker)}</div><h2>{escape(title)}</h2></div>'
            f'<div class="right">{fmt(right) if right else ""}<div class="chips">{ch}</div></div></div>')

CSS += """
table.compact { font-size:6.9pt; } table.compact td, table.compact th { padding:.55mm 1.2mm; }
table.compact .nav { font-size:6.4pt; }
"""
