"""Mesin diagram swimlane (SVG) untuk Panduan UAT — tanpa dependensi luar.

Simpul diletakkan pada grid (lajur peran x kolom langkah). Jenis simpul:
  task      kotak aktivitas pengguna
  auto      aktivitas otomatis sistem (garis putus-putus)
  decision  belah ketupat (keputusan / percabangan)
  gate      segi enam (gerbang persetujuan / ACC)
  doc       dokumen yang terbit (SO, SJ, PR, ...)
  start/end pil hitam (mulai / selesai)
  link      lingkaran rujukan ke alur lain (mis. "→ C")
Panah orthogonal; sisi keluar/masuk bisa diatur (r, l, t, b) dan titik belok manual.
"""
from html import escape

ROLE = {
    "cust":   ("Pelanggan", "#64748B"),
    "sales":  ("Sales", "#2563EB"),
    "sadm":   ("Admin Sales", "#4F46E5"),
    "mgr":    ("Manajer / PIC", "#D97706"),
    "fin":    ("Finance", "#059669"),
    "wh":     ("Gudang", "#0D9488"),
    "whadm":  ("Admin Gudang / Logistik", "#0E7490"),
    "drv":    ("Sopir / Ekspedisi", "#0891B2"),
    "qc":     ("QC", "#9333EA"),
    "mdq":    ("MD Quality", "#7C3AED"),
    "md":     ("MD / R&D", "#DB2777"),
    "dsg":    ("Desainer", "#E11D48"),
    "pur":    ("Pembelian", "#EA580C"),
    "sup":    ("Supplier / Mitra", "#78716C"),
    "smp":    ("Admin Sample", "#C026D3"),
    "ptl":    ("PT pemasok (CST)", "#A16207"),
    "sys":    ("Sistem (otomatis)", "#475569"),
    "whj":    ("Gudang Jakarta (transit)", "#115E59"),
    "whr":    ("Gudang Rancamalang", "#0F766E"),
    "own":    ("Pemilik barang · Sukacita", "#1E40AF"),
}

FONT = "Segoe UI, Arial, sans-serif"


def _wrap(text, max_chars):
    out = []
    for para in str(text).split("\n"):
        words, line = para.split(" "), ""
        for w in words:
            cand = (line + " " + w).strip()
            if len(cand) <= max_chars or not line:
                line = cand
            else:
                out.append(line)
                line = w
        out.append(line)
    return out


class Diagram:
    def __init__(self, lanes, cols, width=1047, lane_h=64, label_w=92, pad=6, title=""):
        self.lanes = lanes            # daftar kunci ROLE atau (kunci, label)
        self.cols = cols
        self.width = width
        self.lane_h = lane_h if isinstance(lane_h, dict) else None
        self.default_h = lane_h if not isinstance(lane_h, dict) else 64
        self.label_w = label_w
        self.pad = pad
        self.col_w = (width - label_w - 2 * pad) / cols
        self.nodes = {}
        self.edges = []
        self.title = title
        self.notes = []
        self._lane_y = {}
        y = 0
        for ln in lanes:
            key = ln[0] if isinstance(ln, tuple) else ln
            h = (self.lane_h or {}).get(key, self.default_h)
            self._lane_y[key] = (y, h)
            y += h
        self.height = y

    # ── simpul ──────────────────────────────────────────────────────────
    def n(self, nid, lane, col, kind, text, num="", dx=0, dy=0, w=None, h=None, fs=None):
        y0, lh = self._lane_y[lane]
        cx = self.label_w + self.pad + (col + 0.5) * self.col_w + dx
        cy = y0 + lh / 2 + dy
        if kind == "decision":
            w = w or min(self.col_w - 10, 112)
            h = h or min(lh - 10, 54)
        elif kind in ("start", "end"):
            w = w or min(self.col_w - 18, 84)
            h = h or 26
        elif kind == "link":
            w = w or 28
            h = h or 28
        elif kind == "doc":
            w = w or min(self.col_w - 12, 104)
            if h is None:
                n_lines = len(_wrap(text, max(8, int((w - 14) / ((fs or 8.9) * 0.54)))))
                h = max(32, 14 + n_lines * 10.6)
        else:
            w = w or min(self.col_w - 16, 126)
            h = h or min(lh - 18, 50)
        self.nodes[nid] = dict(id=nid, lane=lane, col=col, kind=kind, text=text, num=num,
                               cx=cx, cy=cy, w=w, h=h, fs=fs)
        return nid

    def e(self, a, b, label="", fs_=None, ts=None, xm=None, ym=None, via=None, style="solid", lx=None, ly=None,
          color=None):
        self.edges.append(dict(a=a, b=b, label=label, fs=fs_, ts=ts, xm=xm, ym=ym, via=via, style=style,
                               lx=lx, ly=ly, color=color))

    # ── geometri ────────────────────────────────────────────────────────
    def _pt(self, node, side):
        cx, cy, w, h = node["cx"], node["cy"], node["w"], node["h"]
        return {"r": (cx + w / 2, cy), "l": (cx - w / 2, cy), "t": (cx, cy - h / 2), "b": (cx, cy + h / 2)}[side]

    def _auto_sides(self, A, B):
        dx, dy = B["cx"] - A["cx"], B["cy"] - A["cy"]
        if abs(dx) < 4:
            return ("b", "t") if dy > 0 else ("t", "b")
        if dx > 0:
            return ("r", "l")
        return ("b", "b")

    def _path(self, ed):
        A, B = self.nodes[ed["a"]], self.nodes[ed["b"]]
        fs, ts = ed["fs"], ed["ts"]
        if not fs or not ts:
            afs, ats = self._auto_sides(A, B)
            fs, ts = fs or afs, ts or ats
        s, t = self._pt(A, fs), self._pt(B, ts)
        pts = [s]
        if ed["via"]:
            pts += [tuple(p) for p in ed["via"]]
            # sambung titik terakhir ke target secara orthogonal
            lx, ly = pts[-1]
            if ts in ("l", "r"):
                if ly != t[1]:
                    pts.append((lx, t[1]))
            else:
                if lx != t[0]:
                    pts.append((t[0], ly))
            pts.append(t)
        else:
            sh, th = fs in ("l", "r"), ts in ("l", "r")
            if sh and th:
                if abs(s[1] - t[1]) < 0.5:
                    pts.append(t)
                else:
                    xm = ed["xm"] if ed["xm"] is not None else (s[0] + t[0]) / 2
                    pts += [(xm, s[1]), (xm, t[1]), t]
            elif not sh and not th:
                if abs(s[0] - t[0]) < 0.5:
                    pts.append(t)
                else:
                    if ed["ym"] is not None:
                        ym = ed["ym"]
                    elif fs == "b" and ts == "b":
                        ym = max(s[1], t[1]) + 12
                    elif fs == "t" and ts == "t":
                        ym = min(s[1], t[1]) - 12
                    else:
                        ym = (s[1] + t[1]) / 2
                    pts += [(s[0], ym), (t[0], ym), t]
            elif sh and not th:
                pts += [(t[0], s[1]), t]
            else:
                pts += [(s[0], t[1]), t]
        return pts

    # ── render ──────────────────────────────────────────────────────────
    def _node_svg(self, n):
        kind, cx, cy, w, h = n["kind"], n["cx"], n["cy"], n["w"], n["h"]
        lane_color = ROLE.get(n["lane"], ("", "#334155"))[1]
        x, y = cx - w / 2, cy - h / 2
        out = []
        fs = n["fs"] or (8.6 if kind in ("decision",) else 8.9)
        fill, stroke, tcol, dash, sw = "#FFFFFF", lane_color, "#0F172A", "", 1.4
        if kind == "task":
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="6" fill="#FFFFFF" '
                       f'stroke="{stroke}" stroke-width="{sw}"/>')
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="4" height="{h:.1f}" rx="2" fill="{stroke}"/>')
        elif kind == "auto":
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="6" fill="#F8FAFC" '
                       f'stroke="#64748B" stroke-width="1.2" stroke-dasharray="4 3"/>')
            tcol = "#334155"
        elif kind == "decision":
            pts = f"{cx:.1f},{y:.1f} {x + w:.1f},{cy:.1f} {cx:.1f},{y + h:.1f} {x:.1f},{cy:.1f}"
            out.append(f'<polygon points="{pts}" fill="#FFFBEB" stroke="#B45309" stroke-width="1.4"/>')
        elif kind == "gate":
            k = 9
            pts = (f"{x + k:.1f},{y:.1f} {x + w - k:.1f},{y:.1f} {x + w:.1f},{cy:.1f} {x + w - k:.1f},{y + h:.1f} "
                   f"{x + k:.1f},{y + h:.1f} {x:.1f},{cy:.1f}")
            out.append(f'<polygon points="{pts}" fill="#FEF3C7" stroke="#B45309" stroke-width="1.8"/>')
        elif kind == "doc":
            wave = (f"M{x:.1f},{y:.1f} H{x + w:.1f} V{y + h - 5:.1f} "
                    f"C{x + w * 0.75:.1f},{y + h - 11:.1f} {x + w * 0.5:.1f},{y + h + 3:.1f} {x + w * 0.25:.1f},{y + h - 3:.1f} "
                    f"S{x:.1f},{y + h - 6:.1f} {x:.1f},{y + h - 5:.1f} Z")
            out.append(f'<path d="{wave}" fill="#EFF6FF" stroke="#1D4ED8" stroke-width="1.2"/>')
            tcol = "#1E3A8A"
        elif kind in ("start", "end"):
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{h / 2:.1f}" '
                       f'fill="#0F172A" stroke="#0F172A"/>')
            tcol = "#FFFFFF"
        elif kind == "link":
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{w / 2:.1f}" fill="#0F172A"/>')
            tcol = "#FFFFFF"
        # teks
        if kind == "link":
            out.append(f'<text x="{cx:.1f}" y="{cy + 3.5:.1f}" text-anchor="middle" font-size="10" font-weight="700" '
                       f'fill="#FFFFFF" font-family="{FONT}">{escape(n["text"])}</text>')
        else:
            maxc = int((w - (26 if kind == "decision" else 14)) / (fs * 0.54))
            lines = _wrap(n["text"], max(8, maxc))
            lh = fs * 1.18
            ty0 = cy - (len(lines) - 1) * lh / 2 + fs * 0.35
            weight = "600" if kind in ("start", "end", "gate") else "400"
            for i, ln in enumerate(lines):
                out.append(f'<text x="{cx + (2 if kind == "task" else 0):.1f}" y="{ty0 + i * lh:.1f}" text-anchor="middle" '
                           f'font-size="{fs}" font-weight="{weight}" fill="{tcol}" font-family="{FONT}">{escape(ln)}</text>')
        if n["num"]:
            bx, by = (x + 2, y - 5) if kind not in ("decision",) else (cx - 13, y - 3)
            bw = 7 + 5.2 * len(n["num"])
            out.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="11" rx="5.5" fill="{lane_color}"/>')
            out.append(f'<text x="{bx + bw / 2:.1f}" y="{by + 8.2:.1f}" text-anchor="middle" font-size="7.4" '
                       f'font-weight="700" fill="#FFFFFF" font-family="{FONT}">{escape(n["num"])}</text>')
        return "\n".join(out)

    def render(self, scale_note=""):
        W, H = self.width, self.height
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H + 2}" width="100%" '
               f'class="flow" font-family="{FONT}">',
               '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
               'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#334155"/></marker>'
               '<marker id="ahr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
               'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#B91C1C"/></marker>'
               '<marker id="ahg" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
               'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#15803D"/></marker></defs>']
        # lajur
        for i, ln in enumerate(self.lanes):
            key = ln[0] if isinstance(ln, tuple) else ln
            label = ln[1] if isinstance(ln, tuple) else ROLE[key][0]
            color = ROLE.get(key, ("", "#334155"))[1]
            y0, lh = self._lane_y[key]
            bg = "#F8FAFC" if i % 2 == 0 else "#FFFFFF"
            out.append(f'<rect x="0" y="{y0}" width="{W}" height="{lh}" fill="{bg}"/>')
            out.append(f'<line x1="0" y1="{y0 + lh}" x2="{W}" y2="{y0 + lh}" stroke="#E2E8F0" stroke-width="1"/>')
            out.append(f'<rect x="0" y="{y0 + 1}" width="{self.label_w - 4}" height="{lh - 2}" fill="{color}" opacity="0.10"/>')
            out.append(f'<rect x="0" y="{y0 + 1}" width="4" height="{lh - 2}" fill="{color}"/>')
            lines = _wrap(label, 14)
            for j, t in enumerate(lines):
                out.append(f'<text x="10" y="{y0 + lh / 2 - (len(lines) - 1) * 5.5 + j * 11 + 3.5:.1f}" font-size="9.2" '
                           f'font-weight="700" fill="{color}" font-family="{FONT}">{escape(t)}</text>')
        out.append(f'<line x1="{self.label_w - 4}" y1="0" x2="{self.label_w - 4}" y2="{H}" stroke="#CBD5E1"/>')
        # panah
        labels = []
        for ed in self.edges:
            pts = self._path(ed)
            d = "M" + " L".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts)
            col = ed["color"] or "#334155"
            mk = "ahr" if col == "#B91C1C" else ("ahg" if col == "#15803D" else "ah")
            dash = ' stroke-dasharray="5 3"' if ed["style"] == "dash" else ""
            out.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="1.3"{dash} marker-end="url(#{mk})"/>')
            if ed["label"]:
                if ed["lx"] is not None:
                    lx, ly = ed["lx"], ed["ly"]
                else:
                    # label di tengah segmen terpanjang
                    best, bl = 0, -1
                    for k in range(len(pts) - 1):
                        L = abs(pts[k + 1][0] - pts[k][0]) + abs(pts[k + 1][1] - pts[k][1])
                        if L > bl:
                            bl, best = L, k
                    lx = (pts[best][0] + pts[best + 1][0]) / 2
                    ly = (pts[best][1] + pts[best + 1][1]) / 2
                labels.append((lx, ly, ed["label"], col))
        for n in self.nodes.values():
            out.append(self._node_svg(n))
        for lx, ly, t, col in labels:
            lines = t.split("\n")
            wbox = max(len(s) for s in lines) * 4.35 + 8
            hbox = 10.5 * len(lines) + 2
            out.append(f'<rect x="{lx - wbox / 2:.1f}" y="{ly - hbox / 2:.1f}" width="{wbox:.1f}" height="{hbox:.1f}" rx="3" '
                       f'fill="#FFFFFF" stroke="{col}" stroke-width="0.6" opacity="0.96"/>')
            for j, s in enumerate(lines):
                out.append(f'<text x="{lx:.1f}" y="{ly - hbox / 2 + 8.6 + j * 10.5:.1f}" text-anchor="middle" font-size="7.8" '
                           f'font-weight="600" fill="{col}" font-family="{FONT}">{escape(s)}</text>')
        out.append("</svg>")
        return "\n".join(out)


def legend_svg():
    d = Diagram(["sys"], 7, width=1047, lane_h=46, label_w=92)
    d.lanes = [("sys", "Simbol")]
    d.n("a", "sys", 0, "task", "Aktivitas pengguna")
    d.n("b", "sys", 1, "auto", "Proses otomatis sistem")
    d.n("c", "sys", 2, "decision", "Keputusan / cabang?")
    d.n("g", "sys", 3, "gate", "Gerbang ACC / persetujuan")
    d.n("o", "sys", 4, "doc", "Dokumen terbit")
    d.n("s", "sys", 5, "end", "Mulai / Selesai")
    d.n("l", "sys", 6, "link", "C")
    return d.render()
