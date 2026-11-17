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
h3 { font-size:10.5pt; margin:4mm 0 1.6mm; }
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
.sign { display:grid; grid-template-columns:repeat(3,1fr); gap:8mm; margin-top:10mm; }
.sign div { border-top:1px solid #0F172A; padding-top:1mm; font-size:8pt; height:24mm; }
@media screen { body { max-width:210mm; margin:0 auto; padding:8mm; background:#F1F5F9; } .sec, .cover { background:#FFFFFF; padding:10mm; margin-bottom:6mm; box-shadow:0 1px 3px rgba(0,0,0,.12); } .cover { background:#0F172A; } }
"""


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


def img(path: str, cap: str) -> str:
    p = os.path.join(ROOT, path)
    if not path or not os.path.exists(p):
        return ""
    return f'<figure><img src="{escape(path)}" alt=""><figcaption>{escape(cap)}</figcaption></figure>'


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


def scenario_html(d) -> str:
    steps = []
    figs = []
    for s in d.get("langkah", []):
        isi = f'<span class="isi">{fmt(s.get("isi"))}</span>' if s.get("isi") else ""
        steps.append(f'<tr><td class="no">{escape(str(s.get("no")))}</td><td>{role(s.get("peran"))}</td>'
                     f'<td><span class="nav">{escape(s.get("menu") or "")}</span></td>'
                     f'<td>{fmt(s.get("aksi"))}{isi}</td><td>{fmt(s.get("hasil"))}</td><td><span class="cb"></span></td></tr>')
        if s.get("gambar"):
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
  <div class="box"><b class="t">Data awal (Kartu Peserta)</b>{fmt(d.get('data_awal'))}</div>
  <h3>Langkah</h3>
  <table class="steps"><colgroup><col style="width:6%"><col style="width:11%"><col style="width:19%"><col style="width:33%"><col style="width:27%"><col style="width:4%"></colgroup>
  <thead><tr><th>No</th><th>Peran</th><th>Di mana</th><th>Lakukan</th><th>Yang harus terlihat</th><th>✓</th></tr></thead>
  <tbody>{''.join(steps)}</tbody></table>
  <div class="grid2">{cek}{salah}</div>
  {pel}
  {''.join(figs)}
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
    MENU_ROWS = "".join(f'<tr><td><span class="nav">{escape(m)}</span></td><td>{escape(t)}</td></tr>' for m, t in MENU)  # noqa: N806
    ISTILAH_ROWS = "".join(f"<tr><td><b>{escape(k)}</b></td><td>{escape(v)}</td></tr>" for k, v in ISTILAH)  # noqa: N806
    toc ="".join(f'<div><span><b>{escape(d["kode"])}</b>{fmt(d["judul"])}</span><span class="muted">{escape(d.get("peran", ""))} · {d.get("menit", "")} mnt</span></div>' for d in sc)
    a = [d for d in sc if d.get("bagian", "A") == "A"]
    b = [d for d in sc if d.get("bagian") == "B"]
    total = sum(int(d.get("menit") or 0) for d in sc)
    gen = datetime.now().strftime("%d-%m-%Y %H:%M")
    body = f"""
<div class="cover"><div class="band"></div>
  <div class="kicker" style="color:#99F6E4">ERP Kain Nusantara · {DOC_ID}</div>
  <h1>Pelatihan Keuangan</h1>
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
  <p class="muted">Nomor dokumen awal setiap peserta dicetak pelatih dari sistem (perintah penyiapan data). Salin ke sini supaya mudah dicari.</p>
  <table class="grid kartu"><colgroup><col style="width:34%"><col style="width:66%"></colgroup><tbody>
   <tr><td>Nomor peserta · akun</td><td>finance.latih____@kainnusantara.id</td></tr>
   <tr><td>Pelanggan latihan</td><td>Latihan ____ · Toko Kain Peserta ____</td></tr>
   <tr><td>Pemasok latihan</td><td>Latihan ____ · Pemasok Grey Peserta ____</td></tr>
   <tr><td>SO untuk pelunasan (F02)</td><td></td></tr><tr><td>SO untuk bayar sebagian (F03–F04)</td><td></td></tr>
   <tr><td>Tagihan supplier dibayar (F11)</td><td></td></tr><tr><td>Tagihan untuk kontrabon (F12)</td><td></td></tr>
   <tr><td>Dokumen lain (lihat skenario)</td><td></td></tr></tbody></table>
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
    hp = os.path.join(ROOT, NAME + ".html")
    open(hp, "w", encoding="utf-8").write(html)
    open(os.path.join(ROOT, "LEMBAR_LATIHAN.md"), "w", encoding="utf-8").write(lembar(sc))
    print(f"HTML: {hp} ({len(sc)} skenario)")
    if "--html" in sys.argv:
        return
    pdf = os.path.join(ROOT, NAME + ".pdf")
    subprocess.run(["node", os.path.join(HERE, "cetak_pdf.js"), hp, pdf, DOC_ID], check=True)
    print(f"PDF: {pdf}")


if __name__ == "__main__":
    main()
