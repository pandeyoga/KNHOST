"""Rakit Panduan Pelatihan Keuangan (18 Nov 2026) → HTML + PDF A4 + Lembar Latihan (Markdown).

Sumber: `src/skenario/Fxx.json` (langkah, hasil yang harus terlihat, cek buku) dan `uji/hasil/Fxx/hasil.json`
(hasil uji jalan Playwright di layar + cek buku). Gambar diambil dari `uji/hasil/Fxx/*.png`.

Pakai:  python docs/pelatihan/2026-11-18_keuangan/src/bangun.py          → HTML + PDF + LEMBAR_LATIHAN.md
        python docs/pelatihan/2026-11-18_keuangan/src/bangun.py --html   → hanya HTML
PDF dicetak Chromium (Playwright) lewat `src/cetak_pdf.js`.
"""
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
NAME = "Panduan_Pelatihan_Keuangan_ERP_Kain_Nusantara"
DOC_ID = "KN-LATIH-FIN-001"
DATE = "18 November 2026"
START = (8, 30)

BAGIAN = {"A": "Bagian A · Petugas Keuangan (akun Finance peserta)", "B": "Bagian B · Manajer Keuangan (persetujuan, laporan & tutup buku)"}
ROLE_COLOR = {"finance": "#0F766E", "manajer": "#7C3AED", "manager": "#7C3AED", "sales": "#2563EB", "admin": "#334155",
              "gudang": "#B45309", "admin sales": "#0369A1", "pelatih": "#BE123C", "md": "#9333EA", "admin sample": "#4D7C0F"}

CSS = r"""
@page { size: A4; margin: 13mm 12mm 14mm 12mm; }
* { box-sizing: border-box; }
html, body { margin:0; padding:0; background:#FFFFFF; color:#0F172A; font-family:'Segoe UI', 'Inter', Arial, sans-serif; font-size:9.2pt; line-height:1.38; }
.sec { break-before: page; }
h1 { font-size:20pt; margin:0 0 2mm; letter-spacing:-.2px; }
h2 { font-size:14pt; margin:0; }
h3 { font-size:10.5pt; margin:4mm 0 1.6mm; break-after:avoid; }
p { margin:0 0 1.8mm; }
.kicker { font-size:7.6pt; font-weight:700; letter-spacing:.9px; text-transform:uppercase; color:#475569; }
.head { border-bottom:2px solid #0F172A; padding-bottom:1.8mm; margin-bottom:3mm; display:flex; justify-content:space-between; align-items:flex-end; gap:6mm; }
.head .right { text-align:right; }
.chips { display:flex; flex-wrap:wrap; gap:1.4mm; justify-content:flex-end; margin-top:1mm; }
.chip { display:inline-block; border:1px solid #CBD5E1; border-radius:10px; padding:.3mm 2.2mm; font-size:7.6pt; background:#F8FAFC; white-space:nowrap; }
.chip.g { border-color:#86EFAC; background:#F0FDF4; color:#166534; font-weight:600; }
.chip.r { border-color:#FCA5A5; background:#FEF2F2; color:#991B1B; font-weight:600; }
.chip.a { border-color:#FCD34D; background:#FFFBEB; color:#92400E; }
.grid2 { display:grid; grid-template-columns:1fr 1fr; gap:2.4mm; margin:2mm 0; }
.box { border:1px solid #E2E8F0; border-left:3px solid #1D4ED8; border-radius:4px; padding:1.8mm 2.4mm; font-size:8.6pt; background:#FFFFFF; break-inside:avoid; }
.box b.t { display:block; font-size:7.4pt; letter-spacing:.6px; text-transform:uppercase; color:#1E3A8A; margin-bottom:.7mm; }
.box.g { border-left-color:#15803D; } .box.g b.t { color:#166534; }
.box.a { border-left-color:#B45309; } .box.a b.t { color:#92400E; }
.box.r { border-left-color:#B91C1C; background:#FFFBFB; } .box.r b.t { color:#991B1B; }
.box.p { border-left-color:#BE123C; background:#FFF7F9; } .box.p b.t { color:#9F1239; }
.box ul { margin:0; padding-left:4mm; } .box li { margin:0 0 .4mm; }
table { width:100%; border-collapse:collapse; }
table.steps { font-size:8.2pt; table-layout:fixed; }
table.steps thead { display:table-header-group; }
table.steps th { background:#0F172A; color:#FFFFFF; font-weight:600; text-align:left; padding:1.2mm 1.5mm; font-size:7.6pt; }
table.steps td { border-bottom:1px solid #E2E8F0; padding:1.3mm 1.5mm; vertical-align:top; }
table.steps tr { break-inside:avoid; }
table.steps tr:nth-child(even) td { background:#F8FAFC; }
td.no { font-weight:700; text-align:center; }
.role { display:inline-block; padding:0 1.4mm; border-radius:3px; color:#FFFFFF; font-weight:600; font-size:7.2pt; }
.nav { font-family:Consolas, 'Cascadia Mono', monospace; font-size:7.6pt; background:#EEF2FF; padding:0 .8mm; border-radius:2px; overflow-wrap:anywhere; }
.btn { display:inline-block; border:1px solid #94A3B8; border-radius:3px; padding:0 1.1mm; font-size:7.6pt; font-weight:600; background:#FFFFFF; }
.fld { font-weight:600; color:#1E293B; }
.isi { display:block; margin-top:.8mm; color:#334155; }
.cb { display:inline-block; width:3.2mm; height:3.2mm; border:1px solid #64748B; border-radius:.6mm; vertical-align:-0.5mm; }
.ok { color:#166534; font-weight:700; } .bad { color:#991B1B; font-weight:700; } .muted { color:#64748B; }
figure { margin:2.5mm 0 3mm; break-inside:avoid; text-align:center; }
figure img { max-width:100%; max-height:118mm; border:1px solid #CBD5E1; border-radius:3px; }
figcaption { font-size:7.6pt; color:#475569; margin-top:.8mm; }
table.grid { font-size:8.2pt; }
table.grid th { background:#E2E8F0; text-align:left; padding:1.1mm 1.5mm; font-size:7.8pt; }
table.grid td { border-bottom:1px solid #E2E8F0; padding:1.1mm 1.5mm; vertical-align:top; }
table.grid tr { break-inside:avoid; }
.cover { height:268mm; position:relative; background:#0F172A; color:#FFFFFF; padding:20mm 16mm; border-radius:2mm; overflow:hidden; }
.cover h1 { font-size:30pt; line-height:1.1; margin:6mm 0 4mm; }
.cover .sub { font-size:12pt; color:#CBD5E1; max-width:150mm; }
.cover .meta { position:absolute; left:16mm; right:16mm; bottom:16mm; display:grid; grid-template-columns:repeat(3,1fr); gap:5mm; font-size:8.6pt; color:#E2E8F0; }
.cover .meta .lbl { display:block; font-size:7pt; letter-spacing:.8px; text-transform:uppercase; opacity:.7; margin-bottom:1mm; }
.cover .band { position:absolute; right:-40mm; top:-30mm; width:170mm; height:170mm; border-radius:50%; background:radial-gradient(circle at 30% 30%, #0F766E 0%, rgba(15,118,110,0) 70%); opacity:.6; }
.toc div { display:flex; justify-content:space-between; padding:1mm 0; border-bottom:1px dotted #CBD5E1; break-inside:avoid; }
.toc b { display:inline-block; min-width:12mm; }
.kartu td { height:7.5mm; }
svg.flow { width:100%; height:auto; display:block; margin:1mm 0 2.5mm; break-inside:avoid; }
.box.n { border-left-color:#DC2626; margin:2mm 0; } .box.n b.t { color:#991B1B; }
ol.navsteps { margin:.8mm 0 0; padding-left:5mm; } ol.navsteps li { margin:.4mm 0; }
.navgrid { display:grid; grid-template-columns:1fr 1fr; gap:2.4mm; margin:1mm 0 2.5mm; }
.navgrid figure { margin:0; } .navgrid img { max-height:none; }
.navbig figure img { max-height:125mm; }
.sign { display:grid; grid-template-columns:repeat(3,1fr); gap:8mm; margin-top:10mm; }
.sign div { border-top:1px solid #0F172A; padding-top:1mm; font-size:8pt; height:24mm; }
@media screen { body { max-width:210mm; margin:0 auto; padding:8mm; background:#F1F5F9; } .sec, .cover { background:#FFFFFF; padding:10mm; margin-bottom:6mm; box-shadow:0 1px 3px rgba(0,0,0,.12); } .cover { background:#0F172A; } }
"""


KARTU = [
    ("a_dasar:so_lunas", "SO untuk pelunasan penuh", "F02 · F13"),
    ("a_dasar:so_sebagian", "SO untuk bayar sebagian & lebih bayar", "F03 · F04"),
    ("b_piutang:cicilan", "Pelanggan cicilan + rencana pembayaran", "F05"),
    ("b_piutang:izin_kredit", "Pengajuan izin kredit (menunggu Manajer)", "F06"),
    ("c_kas:pd_kas_kecil", "PD kas kecil (uang muka karyawan)", "F07"),
    ("c_kas:titipan_sales", "Titipan tunai sales", "F08"),
    ("c_kas:kwitansi_transfer", "Kwitansi transfer untuk rekonsiliasi", "F10"),
    ("a_dasar:tagihan_bayar", "Tagihan supplier untuk dibayar", "F11"),
    ("a_dasar:tagihan_kontrabon", "Tagihan supplier untuk kontrabon", "F12"),
    ("d_hutang:sample_berbayar", "Pesanan sample berbayar", "F14"),
    ("d_hutang:gaji_susulan", "Proses gaji susulan", "F15"),
    ("e_buku:so_jejak", "SO lunas untuk penelusuran jurnal", "F16"),
]

MENU = [
    ("Keuangan › Beranda Keuangan", "Perlu Tindakan (antrean kerja uang: faktur pajak perlu terbit, uang masuk perlu dicatat, selisih bayar) · Posisi (kas, bank, piutang, hutang) · Analisis"),
    ("Keuangan › Piutang", "Saldo & Umur · Penagihan & Penerimaan (catat uang masuk pelanggan) · Rencana & Denda (cicilan, denda telat) · Titipan & Saldo Kredit (lebih bayar / uang muka) · Kredit & Plafon · Kasus"),
    ("Keuangan › Hutang", "Tagihan supplier (3-way: PO ↔ penerimaan ↔ faktur, bayar) · Kontrabon (tukar faktur) · GR/IR (barang diterima belum ditagih)"),
    ("Keuangan › Kas & Bank", "Rekening & Saldo · Transaksi Kas · Rekonsiliasi (cocokkan mutasi bank dengan buku) · Kas Kecil · Titipan Sales (setoran tunai dari sales)"),
    ("Keuangan › Antar-PT", "Saldo & transaksi antar perusahaan dalam grup (lihat)"),
    ("Akuntansi & Pajak › Buku Besar", "Jurnal (lihat) · Bagan Akun"),
    ("Akuntansi & Pajak › Pajak", "Faktur Keluaran (Finance) · ◆ Faktur Masukan · ◆ PPN & PPh"),
    ("◆ Akuntansi & Pajak › Tutup Buku · Laporan · Aset Tetap", "Daftar periksa & tutup periode · Buka periode · Posting gagal · Laba-Rugi, Neraca & Arus Kas · Profitabilitas · Proyeksi Kas · Anggaran · Konsolidasi"),
    ("Penjualan › Pesanan · Pesanan Sample", "Melihat pesanan (untuk menagih) · menyetujui pembayaran sample berbayar"),
    ("SDM › Penggajian › Setoran & Pajak", "Membayar gaji bersih, setor BPJS & PPh 21 dari proses gaji yang sudah disetujui"),
    ("Pusat Dokumen › Jejak Dokumen", "Menelusuri rantai SO → surat jalan → faktur → pembayaran → jurnal"),
]
ISTILAH = [
    ("Piutang (AR)", "Uang pelanggan yang belum diterima. Lahir saat barang terkirim dengan termin tempo; berkurang saat pembayaran dialokasikan ke pesanan."),
    ("Alokasi", "Menempelkan uang masuk ke pesanan/tagihan tertentu. Uang yang belum dialokasikan menjadi saldo/titipan pelanggan."),
    ("Umur piutang", "Lama piutang sejak jatuh tempo (belum jatuh tempo, 1–30, 31–60, 61–90, >90 hari)."),
    ("Hutang (AP)", "Kewajiban ke supplier. Lahir dari tagihan supplier yang dicocokkan dengan PO dan penerimaan barang (3-way match)."),
    ("GR/IR", "Barang sudah diterima (GR) tetapi tagihannya belum datang (IR). Nilai ini menunggu tagihan supplier."),
    ("Kontrabon", "Tanda terima tukar faktur: supplier menyerahkan faktur, kita memberi tanggal janji bayar."),
    ("Rekonsiliasi bank", "Mencocokkan mutasi rekening koran dengan catatan buku; selisih (biaya admin, bunga) dibukukan."),
    ("Jurnal seimbang", "Setiap transaksi mencatat debit = kredit. Sistem membuat jurnal otomatis dari dokumen; Finance memeriksanya."),
    ("Tutup buku", "Mengunci periode supaya tidak ada transaksi bertanggal di periode itu lagi; dibuka kembali hanya dengan alasan."),
    ("Faktur pajak keluaran", "Faktur PPN untuk penjualan ber-PPN; nomornya diterbitkan dan diekspor ke e-Faktur."),
]


def fmt(s: str) -> str:
    """[[Tombol]] → tombol · *Isian* → tebal · `kode`/menu › → kode."""
    s = escape(str(s or ""))
    s = re.sub(r"\[\[(.+?)\]\]", r'<span class="btn">\1</span>', s)
    s = re.sub(r"\*(.+?)\*", r'<span class="fld">\1</span>', s)
    s = re.sub(r"`(.+?)`", r'<span class="nav">\1</span>', s)
    return s.replace("\n", "<br>")


def role(r: str) -> str:
    key = (r or "").strip().lower()
    col = next((c for k, c in ROLE_COLOR.items() if key.startswith(k)), "#334155")
    return f'<span class="role" style="background:{col}">{escape(r or "")}</span>'


def load():
    sc = []
    for f in sorted(glob.glob(os.path.join(HERE, "skenario", "F*.json"))):
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        res = os.path.join(ROOT, "uji", "hasil", d["kode"], "hasil.json")
        d["_uji"] = json.load(open(res, encoding="utf-8")) if os.path.exists(res) else None
        sc.append(d)
    sc.sort(key=lambda d: (d.get("bagian", "A"), int(re.sub(r"\D", "", d["kode"]) or 0)))
    return sc


def uji_chip(d) -> str:
    u = d.get("_uji")
    if not u:
        return '<span class="chip a">Uji jalan: belum</span>'
    n, ok = len(u["steps"]), sum(1 for s in u["steps"] if s["ok"])
    cls = "g" if u.get("ok") else "r"
    when = (u.get("at") or "")[:16].replace("T", " ")
    return f'<span class="chip {cls}">Uji layar + buku: {ok}/{n} langkah lulus · {escape(when)} UTC</span>'


RINGKAS = "--ringkas" in sys.argv   # versi cetak: tanpa tangkapan layar per langkah


def opt(path: str, max_w: int = 1200) -> str:
    """Salinan JPEG ringan di `gambar/` (dipakai HTML & PDF) — PNG asli uji jalan tetap di uji/hasil/."""
    src = os.path.join(ROOT, path)
    if not path or not os.path.exists(src):
        return ""
    rel = os.path.join("gambar", os.path.relpath(src, os.path.join(ROOT, "uji", "hasil"))).rsplit(".", 1)[0] + ".jpg"
    dst = os.path.join(ROOT, rel)
    if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src):
        from PIL import Image
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        im = Image.open(src).convert("RGB")
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        im.save(dst, "JPEG", quality=72, optimize=True, progressive=True)
    return rel


def img(path: str, cap: str) -> str:
    rel = opt(path)
    if not rel:
        return ""
    return f'<figure><img src="{escape(rel)}" alt=""><figcaption>{escape(cap)}</figcaption></figure>'


def schedule(sc):
    h, m = START
    rows, lunch = [], False
    for d in sc:
        if not lunch and h >= 12:
            rows.append(f'<tr><td>{h:02d}.{m:02d}</td><td colspan="3" class="muted"><i>Istirahat & makan siang (60 menit)</i></td></tr>')
            h += 1
            lunch = True
        mins = int(d.get("menit") or 20)
        rows.append(f"<tr><td>{h:02d}.{m:02d}</td><td><b>{escape(d['kode'])}</b></td><td>{fmt(d['judul'])}</td>"
                    f"<td>{mins} mnt · {escape(d.get('peran', ''))}</td></tr>")
        m += mins
        h, m = h + m // 60, m % 60
    rows.append(f'<tr><td>{h:02d}.{m:02d}</td><td colspan="3"><i>Tanya jawab, evaluasi & penutupan (30 menit)</i></td></tr>')
    return "".join(rows)


FLOW_COLOR = {"finance": "#0F766E", "manajer": "#7C3AED", "manager": "#7C3AED", "sistem": "#475569", "sales": "#2563EB",
              "admin sales": "#0369A1", "gudang": "#B45309", "pembelian": "#9A3412", "admin": "#334155", "pelanggan": "#0E7490",
              "bank": "#1D4ED8", "supplier": "#9A3412", "pemasok": "#9A3412", "md": "#9333EA", "admin sample": "#4D7C0F",
              "pelatih": "#BE123C", "sdm": "#A21CAF", "hr": "#A21CAF"}


def _color(role_name: str) -> str:
    k = (role_name or "").strip().lower()
    return next((c for key, c in FLOW_COLOR.items() if k.startswith(key)), "#334155")


def _wrap(text: str, width: int = 17, lines: int = 3):
    words, out, cur = str(text or "").split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= width:
            cur = f"{cur} {w}".strip()
        else:
            if cur:
                out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1][: width - 1] + "…"
    return out


def flow_svg(alur) -> str:
    """Diagram alur berlajur (satu lajur per peran), simpul kiri → kanan sesuai urutan, cabang = catatan kuning di bawah."""
    if not alur:
        return ""
    lanes = []
    for n in alur:
        if n.get("peran") not in lanes:
            lanes.append(n.get("peran"))
    LW, NW, NH, GAP, LH, TOP = 104, 132, 54, 26, 70, 6
    has_branch = any(n.get("cabang") for n in alur)
    W = LW + len(alur) * (NW + GAP) + 6
    H = TOP + len(lanes) * LH + (64 if has_branch else 8)
    out = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI, Arial, sans-serif" class="flow">',
           '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
           '<path d="M0,0 L10,5 L0,10 z" fill="#334155"/></marker></defs>']
    for i, ln in enumerate(lanes):
        y = TOP + i * LH
        out.append(f'<rect x="0" y="{y}" width="{W}" height="{LH - 4}" rx="6" fill="{"#F8FAFC" if i % 2 == 0 else "#FFFFFF"}" stroke="#E2E8F0"/>')
        out.append(f'<rect x="0" y="{y}" width="{LW - 10}" height="{LH - 4}" rx="6" fill="{_color(ln)}"/>')
        for j, t in enumerate(_wrap(ln, 12, 2)):
            out.append(f'<text x="{(LW - 10) / 2}" y="{y + (LH - 4) / 2 + 5 + (j - (len(_wrap(ln, 12, 2)) - 1) / 2) * 15}" '
                       f'text-anchor="middle" font-size="13" font-weight="700" fill="#FFFFFF">{escape(t)}</text>')
    pos = []
    for k, n in enumerate(alur):
        x = LW + k * (NW + GAP)
        y = TOP + lanes.index(n.get("peran")) * LH + (LH - 4 - NH) / 2
        pos.append((x, y))
        col = _color(n.get("peran"))
        out.append(f'<rect x="{x}" y="{y}" width="{NW}" height="{NH}" rx="8" fill="#FFFFFF" stroke="{col}" stroke-width="2"/>')
        out.append(f'<circle cx="{x + 12}" cy="{y + 12}" r="9" fill="{col}"/><text x="{x + 12}" y="{y + 16}" text-anchor="middle" '
                   f'font-size="11" font-weight="700" fill="#FFFFFF">{k + 1}</text>')
        ls = _wrap(n.get("label"), 16, 3)
        for j, t in enumerate(ls):
            out.append(f'<text x="{x + NW / 2 + 6}" y="{y + NH / 2 + 5 + (j - (len(ls) - 1) / 2) * 14}" text-anchor="middle" '
                       f'font-size="12.5" fill="#0F172A">{escape(t)}</text>')
        if n.get("cabang"):
            by = TOP + len(lanes) * LH + 4
            out.append(f'<line x1="{x + NW / 2}" y1="{y + NH}" x2="{x + NW / 2}" y2="{by}" stroke="#B45309" stroke-dasharray="4 3"/>')
            out.append(f'<rect x="{x - 4}" y="{by}" width="{NW + 8}" height="52" rx="6" fill="#FFFBEB" stroke="#F59E0B"/>')
            cs = _wrap(n["cabang"], 18, 3)
            for j, t in enumerate(cs):
                out.append(f'<text x="{x + NW / 2}" y="{by + 18 + j * 14}" text-anchor="middle" font-size="11.5" fill="#92400E">{escape(t)}</text>')
    for k in range(len(pos) - 1):
        (x1, y1), (x2, y2) = pos[k], pos[k + 1]
        sx, sy, ex, ey = x1 + NW, y1 + NH / 2, x2, y2 + NH / 2
        if abs(sy - ey) < 1:
            out.append(f'<line x1="{sx}" y1="{sy}" x2="{ex - 2}" y2="{ey}" stroke="#334155" stroke-width="1.6" marker-end="url(#ah)"/>')
        else:
            mx = sx + GAP / 2
            out.append(f'<path d="M{sx},{sy} L{mx},{sy} L{mx},{ey} L{ex - 2},{ey}" fill="none" stroke="#334155" stroke-width="1.6" marker-end="url(#ah)"/>')
    out.append("</svg>")
    return "".join(out)


NAV_INDEX = {}


def _nav_index():
    if not NAV_INDEX:
        f = os.path.join(ROOT, "uji", "hasil", "_navigasi", "indeks.json")
        if os.path.exists(f):
            NAV_INDEX.update(json.load(open(f, encoding="utf-8")))
    return NAV_INDEX


def nav_html(d) -> str:
    navs = d.get("navigasi") or []
    if not navs:
        return ""
    role_key = "manager" if d.get("bagian") == "B" else "finance"
    idx = _nav_index()
    rows, figs = [], []
    circ = "①②③④⑤"
    for n in navs:
        parts = [p.strip() for p in str(n.get("menu") or "").split("›") if p.strip()]
        how = " → ".join(f'<b>{circ[i] if i < len(circ) else i + 1}</b> <span class="fld">{escape(p)}</span>' for i, p in enumerate(parts))
        rows.append(f"<li>{how}</li>")
        hit = idx.get(f"{role_key}|{n.get('nav_id')}|{n.get('tab') or ''}") or next(
            (v for k, v in idx.items() if k.endswith(f"|{n.get('nav_id')}|{n.get('tab') or ''}")), None)
        if hit and os.path.exists(os.path.join(ROOT, hit["file"])):
            figs.append(f'<figure class="navfig"><img src="{escape(opt(hit["file"], 900))}" alt=""><figcaption>{escape(n.get("menu") or "")}</figcaption></figure>')
    grid = f'<div class="navgrid">{"".join(figs)}</div>' if figs else ""
    return (f'<div class="box n"><b class="t">Cara menuju layar</b>Klik menu di sisi kiri sesuai nomor (tanda merah pada gambar), '
            f'lalu tab di bagian atas layar:<ol class="navsteps">{"".join(rows)}</ol></div>{grid}')


def money_map() -> str:
    """Peta besar alur uang (satu gambar): siklus penjualan, pembelian, kas & bank → buku besar → laporan → tutup buku."""
    B = []

    def box(x, y, w, h, title, sub, col):
        B.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#FFFFFF" stroke="{col}" stroke-width="2.2"/>'
                 f'<rect x="{x}" y="{y}" width="{w}" height="24" rx="10" fill="{col}"/><rect x="{x}" y="{y + 14}" width="{w}" height="10" fill="{col}"/>'
                 f'<text x="{x + w / 2}" y="{y + 17}" text-anchor="middle" font-size="13" font-weight="700" fill="#FFF">{escape(title)}</text>')
        for j, t in enumerate(sub):
            B.append(f'<text x="{x + w / 2}" y="{y + 43 + j * 16}" text-anchor="middle" font-size="12" fill="#0F172A">{escape(t)}</text>')

    def arrow(x1, y1, x2, y2, label=""):
        B.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#334155" stroke-width="1.8" marker-end="url(#ah2)"/>')
        if label:
            B.append(f'<text x="{(x1 + x2) / 2}" y="{(y1 + y2) / 2 - 6}" text-anchor="middle" font-size="11" fill="#475569">{escape(label)}</text>')

    S, P, K, G, L = "#2563EB", "#9A3412", "#0F766E", "#475569", "#7C3AED"
    box(10, 20, 190, 80, "Penjualan", ["SO terkirim (Sales/Gudang)", "pajak keluaran · F13"], S)
    box(290, 20, 220, 80, "Piutang · F02–F06", ["terima bayar · sebagian ·", "lebih bayar · cicilan · plafon"], S)
    box(10, 140, 190, 80, "Pembelian", ["PO → barang diterima (GR)", "sample berbayar · F14"], P)
    box(290, 140, 220, 80, "Hutang · F11–F12", ["tagihan 3-way · bayar ·", "kontrabon · GR/IR"], P)
    box(590, 80, 200, 100, "Kas & Bank · F07–F10", ["rekening & saldo · kas kecil", "titipan sales · transaksi kas", "rekonsiliasi bank"], K)
    box(290, 260, 220, 70, "Penggajian · F15", ["setoran gaji, BPJS & PPh 21"], "#A21CAF")
    box(860, 20, 200, 80, "Buku Besar · F16", ["jurnal otomatis tiap dokumen", "jejak dokumen"], G)
    box(860, 140, 200, 80, "Laporan · F17", ["Laba-Rugi · Neraca", "Arus Kas · Profitabilitas"], L)
    box(860, 260, 200, 70, "Tutup Buku · F18", ["kunci periode · buka kembali"], L)
    arrow(200, 60, 288, 60, "piutang lahir")
    arrow(200, 180, 288, 180, "hutang lahir")
    arrow(510, 70, 588, 110, "uang masuk")
    arrow(510, 180, 588, 155, "uang keluar")
    arrow(510, 290, 590, 178, "")
    arrow(790, 120, 858, 70, "jurnal")
    arrow(960, 100, 960, 138)
    arrow(960, 220, 960, 258)
    return ('<svg viewBox="0 0 1070 340" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI, Arial, sans-serif" class="flow">'
            '<defs><marker id="ah2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            '<path d="M0,0 L10,5 L0,10 z" fill="#334155"/></marker></defs>' + "".join(B) + "</svg>")


def scenario_html(d) -> str:
    steps = []
    figs = []
    for s in d.get("langkah", []):
        isi = f'<span class="isi">{fmt(s.get("isi"))}</span>' if s.get("isi") else ""
        steps.append(f'<tr><td class="no">{escape(str(s.get("no")))}</td><td>{role(s.get("peran"))}</td>'
                     f'<td><span class="nav">{escape(s.get("menu") or "")}</span></td>'
                     f'<td>{fmt(s.get("aksi"))}{isi}</td><td>{fmt(s.get("hasil"))}</td><td><span class="cb"></span></td></tr>')
        if s.get("gambar") and not RINGKAS:
            aksi = re.sub(r"[\[\]*`]", "", str(s.get("aksi") or ""))[:110]
            figs.append(img(s["gambar"], f"{d['kode']} langkah {s.get('no')} — {aksi}"))
    def lst(items):
        return "<ul>" + "".join(f"<li>{fmt(x)}</li>" for x in items or []) + "</ul>"
    cek = f'<div class="box g"><b class="t">Cek di buku (jurnal & saldo)</b>{lst(d.get("cek_buku"))}</div>' if d.get("cek_buku") else ""
    salah = f'<div class="box a"><b class="t">Kesalahan yang sering terjadi</b>{lst(d.get("kesalahan_umum"))}</div>' if d.get("kesalahan_umum") else ""
    pel = f'<div class="box p"><b class="t">Catatan pelatih</b>{fmt(d.get("catatan_pelatih"))}</div>' if d.get("catatan_pelatih") else ""
    return f"""
<section class="sec" id="{escape(d['kode'])}">
  <div class="head"><div><div class="kicker">{escape(BAGIAN.get(d.get('bagian', 'A'), ''))}</div>
    <h2>{escape(d['kode'])} · {fmt(d['judul'])}</h2></div>
    <div class="right"><div class="chips"><span class="chip">{escape(d.get('peran', ''))}</span><span class="chip">{escape(str(d.get('menit', '')))} menit</span></div>
    <div class="chips">{uji_chip(d)}</div></div></div>
  <div class="grid2"><div class="box"><b class="t">Tujuan</b>{fmt(d.get('tujuan'))}</div>
    <div class="box"><b class="t">Kapan dipakai</b>{fmt(d.get('kapan'))}</div></div>
  {('<h3>Alur</h3>' + flow_svg(d.get('alur'))) if d.get('alur') else ''}
  {nav_html(d)}
  <div class="box"><b class="t">Data awal (Kartu Peserta)</b>{fmt(d.get('data_awal'))}</div>
  <h3>Langkah</h3>
  <table class="steps"><colgroup><col style="width:6%"><col style="width:11%"><col style="width:19%"><col style="width:33%"><col style="width:27%"><col style="width:4%"></colgroup>
  <thead><tr><th>No</th><th>Peran</th><th>Di mana</th><th>Lakukan</th><th>Yang harus terlihat</th><th>✓</th></tr></thead>
  <tbody>{''.join(steps)}</tbody></table>
  <div class="grid2">{cek}{salah}</div>
  {pel}
  {('<h3>Tangkapan layar per langkah</h3>' + ''.join(figs)) if figs else ''}
</section>"""


def rekap(sc) -> str:
    rows = []
    for d in sc:
        u = d.get("_uji")
        if u:
            n, ok = len(u["steps"]), sum(1 for s in u["steps"] if s["ok"])
            st = f'<span class="{"ok" if u.get("ok") else "bad"}">{"LULUS" if u.get("ok") else "GAGAL"}</span>'
            det = f"{ok}/{n} langkah · 5xx: {len(u.get('http_5xx') or [])} · galat konsol: {len(u.get('console_errors') or [])}"
            fail = "; ".join(f"{s['no']}: {s['info'][:120]}" for s in u["steps"] if not s["ok"])
        else:
            st, det, fail = '<span class="muted">belum diuji</span>', "", ""
        rows.append(f"<tr><td><b>{escape(d['kode'])}</b></td><td>{fmt(d['judul'])}</td><td>{st}</td><td>{escape(det)}"
                    f"{'<br><span class=bad>' + escape(fail) + '</span>' if fail else ''}</td>"
                    f"<td class='muted'>{escape((d.get('uji') or {}).get('berkas', ''))}</td></tr>")
    return "".join(rows)


def build_html(sc) -> str:
    KARTU_ROWS = "".join(f'<tr><td>{escape(lbl)} <span class="muted">({escape(sk)})</span><br><span class="nav">{escape(k)}</span></td><td></td></tr>'  # noqa: N806
                         for k, lbl, sk in KARTU)
    MENU_ROWS = "".join(f'<tr><td><span class="nav">{escape(m)}</span></td><td>{escape(t)}</td></tr>' for m, t in MENU)  # noqa: N806
    ISTILAH_ROWS = "".join(f"<tr><td><b>{escape(k)}</b></td><td>{escape(v)}</td></tr>" for k, v in ISTILAH)  # noqa: N806
    NAV_FIGS = "".join(  # noqa: N806
        f'<figure class="navfig"><img src="{escape(opt(v["file"], 900))}" alt=""><figcaption>{escape(v.get("menu") or k)}'
        f'{" (Manajer)" if v.get("role") == "manager" else ""}</figcaption></figure>'
        for k, v in sorted(_nav_index().items(), key=lambda kv: (kv[1].get("role") != "finance", kv[1].get("menu") or ""))
        if os.path.exists(os.path.join(ROOT, v["file"])))
    toc ="".join(f'<div><span><b>{escape(d["kode"])}</b>{fmt(d["judul"])}</span><span class="muted">{escape(d.get("peran", ""))} · {d.get("menit", "")} mnt</span></div>' for d in sc)
    a = [d for d in sc if d.get("bagian", "A") == "A"]
    b = [d for d in sc if d.get("bagian") == "B"]
    total = sum(int(d.get("menit") or 0) for d in sc)
    gen = datetime.now().strftime("%d-%m-%Y %H:%M")
    body = f"""
<div class="cover"><div class="band"></div>
  <div class="kicker" style="color:#99F6E4">ERP Kain Nusantara · {DOC_ID}</div>
  <h1>Pelatihan Keuangan{'<br><span style="font-size:15pt;color:#99F6E4">Versi ringkas untuk dicetak</span>' if RINGKAS else ''}</h1>
  <div class="sub">Panduan langkah demi langkah untuk petugas keuangan dan manajer: uang masuk & piutang, kas & bank,
  hutang & pajak, buku besar, laporan, dan tutup buku — setiap skenario sudah dijalankan di layar dan dicocokkan dengan buku.</div>
  <div class="meta"><div><span class="lbl">Tanggal</span>{DATE}</div><div><span class="lbl">Isi</span>{len(sc)} skenario · ±{total // 60} jam {total % 60} menit praktik</div>
  <div><span class="lbl">Disusun</span>{gen} WIB</div></div></div>

<section class="sec"><div class="head"><div><div class="kicker">Mulai di sini</div><h2>Cara memakai panduan ini</h2></div></div>
  <div class="grid2">
   <div class="box"><b class="t">Satu peserta = satu akun</b>Setiap peserta masuk dengan akun Finance sendiri
     <span class="nav">finance.latihNN@kainnusantara.id</span> (NN = nomor peserta, sandi dibagikan pelatih) dan hanya melihat
     PT Sukacita. Dokumen latihan Anda memakai nama <b>Latihan NN</b>: pelanggan <i>Latihan NN · Toko Kain Peserta NN</i>
     dan pemasok <i>Latihan NN · Pemasok Grey Peserta NN</i>. Cari dokumen Anda dengan nama itu — jangan memproses dokumen peserta lain.</div>
   <div class="box"><b class="t">Cara membaca tabel langkah</b><span class="nav">Menu › Sub-menu › Tab</span> = tempat layar ·
     <span class="btn">Tombol</span> = tombol yang diklik persis seperti tulisannya · <span class="fld">Isian</span> = kolom yang diisi ·
     kolom <b>Yang harus terlihat</b> = bukti langkah berhasil. Centang <span class="cb"></span> bila sudah sama.</div>
   <div class="box g"><b class="t">Sudah diuji</b>Setiap skenario dijalankan otomatis di layar (browser) dengan akun peran yang sama,
     lalu angkanya dicocokkan dengan jurnal & saldo. Hasilnya tertera di kepala tiap skenario dan di Rekap Uji.</div>
   <div class="box a"><b class="t">Bila hasil berbeda</b>Jangan ulangi langkah berkali-kali. Catat nomor dokumen + tangkapan layar
     di Lembar Latihan (kolom Temuan) dan beri tahu pelatih. Uang yang sudah tercatat tidak dihapus — dikoreksi dengan dokumen pembalik.</div>
  </div>
  <h3>Daftar skenario</h3><div class="toc">{toc}</div>
</section>

<section class="sec"><div class="head"><div><div class="kicker">Jadwal</div><h2>Jadwal satu hari (mulai {START[0]:02d}.{START[1]:02d} WIB)</h2></div></div>
  <table class="grid"><colgroup><col style="width:12%"><col style="width:9%"><col style="width:52%"><col style="width:27%"></colgroup>
  <thead><tr><th>Jam</th><th>Kode</th><th>Skenario</th><th>Durasi · peran</th></tr></thead><tbody>{schedule(sc)}</tbody></table>
  <h3>Kartu Peserta (diisi saat pembukaan)</h3>
  <p class="muted">Nomor dokumen awal setiap peserta dicetak pelatih dari sistem (Kartu Peserta). Baris abu-abu = nama kunci di kartu. Salin nomornya ke sini supaya mudah dicari.</p>
  <table class="grid kartu"><colgroup><col style="width:34%"><col style="width:66%"></colgroup><tbody>
   <tr><td>Nomor peserta · akun</td><td>finance.latih____@kainnusantara.id</td></tr>
   <tr><td>Pelanggan latihan</td><td>Latihan ____ · Toko Kain Peserta ____</td></tr>
   <tr><td>Pemasok latihan</td><td>Latihan ____ · Pemasok Grey Peserta ____</td></tr>
{KARTU_ROWS}</tbody></table>
</section>

<section class="sec"><div class="head"><div><div class="kicker">Gambaran besar</div><h2>Alur uang di ERP — di mana tiap skenario terjadi</h2></div></div>
  <p>Setiap dokumen operasional (pesanan, penerimaan barang, tagihan, kas) otomatis membuat jurnal. Tugas keuangan: mencatat uang
  masuk/keluar, mencocokkannya dengan dokumen dan bank, lalu memastikan buku seimbang sebelum laporan dan tutup buku.</p>
  {money_map()}
  <div class="grid2"><div class="box"><b class="t">Siklus penjualan → piutang</b>Barang terkirim dengan termin tempo → piutang lahir →
   Finance mencatat uang masuk & mengalokasikannya → piutang turun, kas/bank naik → jurnal otomatis.</div>
   <div class="box"><b class="t">Siklus pembelian → hutang</b>Barang diterima gudang (GR) → tagihan supplier dicocokkan PO & penerimaan
   (3-way) → hutang lahir → dibayar langsung atau lewat kontrabon → jurnal otomatis.</div></div>
</section>

<section class="sec"><div class="head"><div><div class="kicker">Panduan navigasi</div><h2>Cara menuju layar keuangan</h2></div></div>
  <p>Menu ada di sisi kiri. Klik nama grup (tanda <b>①</b>) supaya isinya terbuka, klik menu (<b>②</b>), lalu pilih tab di bagian atas
  layar (<b>③</b>). Kolom <span class="fld">Cari menu…</span> di atas menu (Ctrl+K) juga bisa dipakai: ketik nama layar, tekan Enter.
  Di kiri atas layar ada jejak lokasi (Beranda › grup › menu) — klik untuk kembali.</p>
  <div class="navgrid">{NAV_FIGS}</div>
</section>

<section class="sec"><div class="head"><div><div class="kicker">Orientasi</div><h2>Peta menu keuangan</h2></div></div>
  <p>Menu di sisi kiri mengikuti izin akun. Akun Finance melihat menu berikut (Manajer melihat semuanya ditambah yang bertanda ◆).</p>
  <table class="grid"><colgroup><col style="width:30%"><col style="width:70%"></colgroup>
  <thead><tr><th>Menu</th><th>Tab · dipakai untuk</th></tr></thead><tbody>{MENU_ROWS}</tbody></table>
  <h3>Istilah yang sering muncul</h3>
  <table class="grid"><colgroup><col style="width:24%"><col style="width:76%"></colgroup><tbody>{ISTILAH_ROWS}</tbody></table>
</section>
"""
    if a:
        body += f'<section class="sec"><div class="head"><div><div class="kicker">Bagian A</div><h2>{escape(BAGIAN["A"])}</h2></div></div>' \
                f'<p>{len(a)} skenario untuk petugas keuangan harian. Dikerjakan dengan akun Finance peserta.</p></section>'
        body += "".join(scenario_html(d) for d in a)
    if b:
        body += f'<section class="sec"><div class="head"><div><div class="kicker">Bagian B</div><h2>{escape(BAGIAN["B"])}</h2></div></div>' \
                f'<p>{len(b)} skenario untuk manajer. Penutupan periode memengaruhi semua pengguna — di pelatihan diperagakan pelatih.</p></section>'
        body += "".join(scenario_html(d) for d in b)
    body += f"""
<section class="sec"><div class="head"><div><div class="kicker">Bukti</div><h2>Rekap uji jalan (layar + buku)</h2></div></div>
  <p>Setiap baris = satu skenario yang dijalankan otomatis di browser (Playwright) dengan akun peran, lalu dicocokkan dengan jurnal,
  saldo, dan status di server. Galat 5xx = galat server selama uji.</p>
  <table class="grid"><colgroup><col style="width:8%"><col style="width:34%"><col style="width:10%"><col style="width:30%"><col style="width:18%"></colgroup>
  <thead><tr><th>Kode</th><th>Skenario</th><th>Hasil</th><th>Rincian</th><th>Skrip uji</th></tr></thead><tbody>{rekap(sc)}</tbody></table>
  <h3>Evaluasi pelatihan</h3>
  <table class="grid kartu"><tbody><tr><td style="width:40%">Skenario yang paling membantu</td><td></td></tr>
   <tr><td>Skenario yang masih membingungkan</td><td></td></tr><tr><td>Temuan / usulan perbaikan layar</td><td></td></tr></tbody></table>
  <div class="sign"><div>Peserta</div><div>Pelatih</div><div>Pemilik / Manajer Keuangan</div></div>
</section>"""
    return (f'<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>Pelatihan Keuangan</title><style>{CSS}</style></head><body>{body}</body></html>")


def lembar(sc) -> str:
    out = [f"# Lembar Latihan — Pelatihan Keuangan ({DATE})", "",
           "Nama peserta: ____________________ · Akun: finance.latih____@kainnusantara.id", "",
           "Centang langkah yang hasilnya sama dengan kolom *Yang harus terlihat*. Bila berbeda, tulis nomor dokumen & apa yang terlihat.", ""]
    for d in sc:
        judul = re.sub(r"[\[\]*`]", "", d["judul"])
        out += [f"## {d['kode']} · {judul}", "", "| No | Lakukan | Yang harus terlihat | Sama? | Temuan |", "|---|---|---|---|---|"]
        for s in d.get("langkah", []):
            clean = lambda x: re.sub(r"[\[\]*`]", "", str(x or "")).replace("|", "/").replace("\n", " ")
            out.append(f"| {s.get('no')} | {clean(s.get('aksi'))} | {clean(s.get('hasil'))} | ☐ | |")
        out.append("")
    return "\n".join(out) + "\n"


def main() -> None:
    sc = load()
    html = build_html(sc)
    name = NAME + ("_Ringkas" if RINGKAS else "")
    hp = os.path.join(ROOT, name + ".html")
    open(hp, "w", encoding="utf-8").write(html)
    if not RINGKAS:
        open(os.path.join(ROOT, "LEMBAR_LATIHAN.md"), "w", encoding="utf-8").write(lembar(sc))
    print(f"HTML: {hp} ({len(sc)} skenario)")
    if "--html" in sys.argv:
        return
    pdf = os.path.join(ROOT, name + ".pdf")
    subprocess.run(["node", os.path.join(HERE, "cetak_pdf.js"), hp, pdf, DOC_ID], check=True)
    print(f"PDF: {pdf}")


if __name__ == "__main__":
    main()
