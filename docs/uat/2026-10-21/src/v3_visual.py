"""UAT v3.0 — visualisasi: strip alur per skenario (tahap per peran + menu + tombol) dan peta menu per peran.

Semua diturunkan dari data langkah (v3_scenarios) supaya gambar selalu sama dengan tabel langkah.
"""
import re
from html import escape

from page import ROLE_COLORS, fmt

CSS = """
.flowstrip { display:flex; flex-wrap:wrap; align-items:stretch; gap:1.2mm 0; margin:1.6mm 0 2.6mm 0; }
.fs-stage { width:44mm; border:1px solid #CBD5E1; border-top-width:3px; border-radius:2mm; padding:1.2mm 1.6mm; background:#FFF;
  font-size:7pt; line-height:1.3; break-inside:avoid; }
.fs-stage .fs-role { font-weight:700; font-size:7.4pt; }
.fs-stage .fs-dev { float:right; font-size:6.2pt; font-weight:700; border-radius:2mm; padding:0 1.2mm; color:#FFF; }
.fs-stage .fs-no { color:#64748B; font-size:6.4pt; }
.fs-stage .fs-menu { margin-top:.6mm; }
.fs-stage .fs-menu .nav { font-size:6.4pt; }
.fs-stage .fs-btns { margin-top:.6mm; color:#334155; }
.fs-stage .fs-btns .btn { font-size:6.2pt; margin:0 .3mm .4mm 0; }
.fs-stage .fs-ui { margin-top:.6mm; font-size:6.3pt; }
.fs-arrow { width:5mm; display:flex; align-items:center; justify-content:center; color:#94A3B8; font-size:11pt; }
.menumap { display:grid; grid-template-columns: 74mm 1fr; gap:6mm; align-items:start; }
.phone { border:2mm solid #0F172A; border-radius:6mm; background:#F8FAFC; overflow:hidden; font-size:6.3pt; line-height:1.22; }
.phone .ph-top { background:linear-gradient(90deg,#1D4ED8,#6D28D9); color:#FFF; padding:1.6mm 3mm; font-weight:700; font-size:7.6pt; }
.phone .ph-top span { display:block; font-weight:400; font-size:6.6pt; opacity:.85; }
.phone .ph-body { padding:1.4mm 2mm; }
.phone .ph-sec { background:#FFF; border:1px solid #E2E8F0; border-radius:2mm; padding:.9mm 1.6mm; margin-bottom:1.1mm; }
.phone .ph-sec b { display:block; font-size:6.8pt; margin-bottom:.2mm; color:#1E3A8A; }
.phone .ph-sec li { margin:0 0 .2mm 0; }
.phone .ph-sec ul { margin:0; padding-left:3.2mm; }
.phone .ph-tabs { display:grid; grid-template-columns: repeat(5, 1fr); border-top:1px solid #E2E8F0; background:#FFF; text-align:center;
  font-size:6.4pt; padding:1.4mm 0; }
.phone .ph-tabs div b { display:block; font-size:9pt; color:#1D4ED8; }
"""

DEVICE = {"Sales": ("HP", "#2563EB")}


def _role(r):
    return r[0] if isinstance(r, tuple) else r


def _menus(navs):
    out = []
    for n in navs:
        m = re.match(r"\s*HP:\s*tab \*\*([^*]+)\*\*(?:\s*›\s*\*\*([^*]+)\*\*)?", n)
        if m:
            label = "HP › " + m.group(1) + (f" › {m.group(2)}" if m.group(2) else "")
        else:
            b = re.search(r"`([^`]+)`", n)
            label = b.group(1) if b else ""
        if label and label not in out:
            out.append(label)
    return out[:2]


def _buttons(navs, limit=6):
    seen = []
    for n in navs:
        for b in re.findall(r"\[\[([^\]]+)\]\]", n):
            if b not in seen:
                seen.append(b)
    return seen[:limit]


def stages(rows):
    out = []
    for i, (role, nav, act, exp, ui) in enumerate(rows, 1):
        r = _role(role)
        if out and out[-1]["role"] == r:
            st = out[-1]
            st["to"] = i
        else:
            st = {"role": r, "from": i, "to": i, "navs": [], "ui": []}
            out.append(st)
        st["navs"].append(nav)
        st["ui"].append(ui)
    return out


def flow_strip(code, rows):
    parts = ['<div class="flowstrip">']
    sts = stages(rows)
    for k, st in enumerate(sts):
        color = ROLE_COLORS.get(st["role"].split(" ·")[0].split(" (")[0].split(" /")[0], "#334155")
        dev, dcol = DEVICE.get(st["role"], ("Desktop", "#475569"))
        no = f"{code}-{st['from']:02d}" + (f" s.d. {st['to']:02d}" if st["to"] != st["from"] else "")
        menus = _menus(st["navs"]) or ["layar yang sama"]
        btns = _buttons(st["navs"])
        checked = sum(1 for u in st["ui"] if u)
        ui = (f'<span class="t-ok">✓ {checked}/{len(st["ui"])} dicek di layar</span>' if checked
              else '<span class="t-na">○ belum dicek</span>')
        parts.append(
            f'<div class="fs-stage" style="border-top-color:{color}"><span class="fs-dev" style="background:{dcol}">{dev}</span>'
            f'<div class="fs-role" style="color:{color}">{escape(st["role"])}</div><div class="fs-no">{no}</div>'
            f'<div class="fs-menu">{"<br>".join(fmt("`" + m + "`") for m in menus)}</div>'
            + (f'<div class="fs-btns">{"".join(fmt("[[" + b + "]]") for b in btns)}</div>' if btns else "")
            + f'<div class="fs-ui">{ui}</div></div>')
        if k < len(sts) - 1:
            parts.append('<div class="fs-arrow">➜</div>')
    parts.append("</div>")
    return "".join(parts)


def role_menus(scenarios):
    """{peran: {menu: [kode alur]}} untuk semua peran desktop (Sales di HP ditulis terpisah)."""
    out = {}
    for sc in scenarios:
        code, rows = sc[0], sc[-1]()
        for role, nav, act, exp, ui in rows:
            r = _role(role)
            if r in ("Sales", "Sistem", "Supplier", "Mitra"):
                continue
            for m in _menus([nav]):
                out.setdefault(r, {}).setdefault(m, [])
                if code not in out[r][m]:
                    out[r][m].append(code)
    return out


PHONE = [
    ("Beranda", ["[Buat Pesanan Baru]", "Tanya KN", "Pesanan menunggu ACC", "Performa Saya (komisi, penjualan, tertagih)"]),
    ("Katalog", ["Cari produk, SKU, warna", "kartu produk → [Pilih]", "Order biasa / Order sample · Per yard / Per Roll",
                 "Genapkan ke Roll Utuh"]),
    ("Keranjang", ["[Lanjut ke Checkout]", "1 Pelanggan & Alamat", "2 Termin & Lot · Minta Harga Khusus · Request QC",
                   "3 Review · Kirim / Ambil · Faktur Pajak → [Buat Sales Order]"]),
    ("Pesanan", ["cari nomor / pelanggan · Semua / Aktif / Selesai / Batal", "kartu SO: Persetujuan ([Ajukan Harga Khusus], "
                 "[Minta Persetujuan Kredit])", "[Ajukan koreksi] · [Catat bayar] · [Ajukan retur]", "Perjalanan Pesanan"]),
    ("Lainnya", ["Pesanan & harga: Koreksi & Amandemen · Pesanan Khusus (OD) · Pesanan Sample · Retur Penjualan · "
                 "Minta Harga Khusus · Harga Khusus Saya · Daftar Harga",
                 "Pelanggan & lapangan: Dasbor Pesanan · Pelanggan (CRM) · Penagihan & Target · Prospek · Kunjungan Sales",
                 "Stok & pemenuhan: Stok & ATP · Permintaan Internal (PIN)", "Tampilan Desktop · Keluar"]),
]


def phone_mock():
    secs = "".join(f'<div class="ph-sec"><b>{escape(t)}</b><ul>{"".join(f"<li>{escape(x)}</li>" for x in items)}</ul></div>'
                   for t, items in PHONE)
    tabs = "".join(f"<div><b>●</b>{t}</div>" for t, _ in PHONE)
    return (f'<div class="phone"><div class="ph-top">Halo, Ayu<span>Sukacita · aplikasi HP Sales</span></div>'
            f'<div class="ph-body">{secs}</div><div class="ph-tabs">{tabs}</div></div>')


def menu_page(scenarios, head):
    rm = role_menus(scenarios)
    order = ["Admin Sales", "Manajer", "Finance", "Finance / Manajer", "Gudang", "Admin Gudang", "QC", "MD Quality", "MD",
             "Desainer", "PIC", "R&D", "Pembelian", "Admin Sample", "CST"]
    roles = [r for r in order if r in rm] + [r for r in rm if r not in order]
    rows = []
    for r in roles:
        color = ROLE_COLORS.get(r.split(" ·")[0].split(" /")[0], "#334155")
        menus = "".join(f'<div style="margin-bottom:.5mm">{fmt("`" + m + "`")} <span class="small">{" ".join(v)}</span></div>'
                        for m, v in sorted(rm[r].items(), key=lambda kv: -len(kv[1]))[:7])
        rows.append(f'<tr><td><span class="role" style="background:{color}">{escape(r)}</span></td><td>{menus}</td></tr>')
    return (f'<section class="sec">{head}'
            f'<div class="menumap"><div><h3 style="margin-top:0">Sales — aplikasi HP (tampil otomatis di layar HP)</h3>{phone_mock()}</div>'
            f'<div><h3 style="margin-top:0">Peran lain — desktop (menu kiri › antrean / tab)</h3>'
            f'<table class="grid"><colgroup><col style="width:20%"><col style="width:80%"></colgroup>'
            f'<thead><tr><th>Peran</th><th>Menu yang dipakai · alur</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></div></section>')
