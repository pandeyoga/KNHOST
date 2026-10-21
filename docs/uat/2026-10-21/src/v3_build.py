"""Rakit Panduan UAT v3.0 (satu alur lurus per cabang, 1 hari mulai 09.00) → HTML + PDF A4 lanskap.

Pemakaian:  python v3_build.py          -> HTML + PDF + LEMBAR_HASIL_UAT_v3.md
            python v3_build.py --html   -> hanya HTML
Nomor halaman di daftar alur dicari lewat PyMuPDF di container backend (bila tersedia); tanpa itu kolom halaman kosong.
"""
import json
import os
import re
import subprocess
import sys
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import page  # noqa: E402
from page import head, fmt, role_cell  # noqa: E402
import sched  # noqa: E402
import v3_scenarios as V  # noqa: E402
import v3_visual as VIS  # noqa: E402
import v3_flow as FLOW  # noqa: E402

OUT_DIR = os.path.abspath(os.path.join(HERE, ".."))
NAME = "Panduan_UAT_E2E_ERP_Kain_Nusantara_v3.0"
DOC_ID = "KN-UAT-E2E-003"
DATE = "22 Oktober 2026"
PAGES_JSON = os.path.join(HERE, "v3_pages.json")
CSS = page.CSS.replace("Panduan UAT End-to-End v2.0 · KN-UAT-E2E-002", f"Panduan UAT End-to-End v3.0 · {DOC_ID}") + """
table.v3 { font-size:7.5pt; table-layout:fixed; }
table.v3 th { background:#0F172A; color:#FFF; font-weight:600; text-align:left; padding:1.1mm 1.4mm; font-size:7.1pt; }
table.v3 td { border-bottom:1px solid #E2E8F0; padding:1.05mm 1.4mm; vertical-align:top; }
table.v3 tr { break-inside: avoid; } table.v3 thead { display: table-header-group; }
table.v3 tr:nth-child(even) td { background:#F8FAFC; }
.res { font-size:6.9pt; color:#334155; line-height:1.6; } .res .ln { display:inline-block; border-bottom:1px solid #94A3B8; width:20mm; }
.grp1 { background:#EFF6FF; } .grp2 { background:#FFF7ED; }
.big { font-size:9.2pt; } .big li { margin-bottom:1.1mm; }
.dev { display:inline-block; border-radius:2mm; padding:0 1.2mm; font-size:6.2pt; font-weight:700; color:#FFF; margin-top:.4mm; }
""" + VIS.CSS
GROUP = {1: "Kelompok 1 · Penjualan & Retur", 2: "Kelompok 2 · Hulu, Pengadaan & Sample"}
UI_FULL = {"full": ("g", "Cek UI: seluruh langkah sudah dijalankan di layar"),
           "partial": ("a", "Cek UI: sebagian langkah"),
           "none": ("r", "Cek UI: belum dijalankan di layar")}


def ui_cell(u):
    if u in ("S1", "S2"):
        return f'<span class="t-ok">✓ dicek di layar ({u})</span>'
    if u == "HP":
        return '<span class="t-ok">✓ dicek di layar HP</span>'
    if u and u.startswith("="):
        return f'<span class="t-ok">✓ langkah sama dicek di {u[1:]}</span>'
    if u and re.fullmatch(r"S\d+", u):
        return f'<span class="t-ok">✓ dicek di layar ({u})</span>'
    return '<span class="t-na">○ belum dicek di layar</span>'


def res_cell():
    return ('<span class="res"><span class="cb"></span>Lulus <span class="cb"></span>Gagal <span class="cb"></span>Terblokir<br>'
            'No. dok <span class="ln"></span></span>')


def steps_table(code, rows):
    widths = (5.5, 10.5, 17, 25, 22, 8, 12)
    cols = ["No", "Peran · akun", "Buka (menu › antrean › tombol)", "Yang dilakukan / diisi", "Hasil yang harus terlihat",
            "Cek UI", "Hasil UAT"]
    out = ['<table class="v3"><colgroup>' + "".join(f'<col style="width:{w}%">' for w in widths) + "</colgroup><thead><tr>" +
           "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead><tbody>"]
    for i, (role, nav, act, exp, ui) in enumerate(rows, 1):
        acct = None
        if isinstance(role, tuple):
            role, acct = role
        dev = '<span class="dev" style="background:#2563EB">HP</span>' if role == "Sales" else '<span class="dev" style="background:#64748B">Desktop</span>'
        out.append(f'<tr><td class="no">{code}-{i:02d}</td><td>{role_cell(role, acct)}{dev}</td><td>{fmt(nav)}</td>'
                   f"<td>{fmt(act)}</td><td>{fmt(exp)}</td><td>{ui_cell(ui)}</td><td>{res_cell()}</td></tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def _end(start, minutes):
    h, m = map(int, start.split("."))
    t = h * 60 + m + minutes
    return f"{t // 60:02d}.{t % 60:02d}"


def cover():
    return f"""<section class="cover"><div class="band"></div>
<div class="kicker" style="color:#93C5FD">{DOC_ID} · versi 3.0 · {DATE}</div>
<h1>Panduan UAT End-to-End<br>ERP Kain Nusantara</h1>
<p class="sub">16 alur uji · 1 hari · 09.00–17.00 WIB</p>
<div class="lanes">{"".join(f'<div style="background:{c};color:#fff">{escape(t)}</div>' for c, t in (("#1D4ED8", "16 alur uji"), ("#0E7490", "1 hari · mulai 09.00 WIB"), ("#B45309", "2 kelompok paralel")))}</div>
<div class="meta">
<div><span class="lbl">Pelaksanaan</span>1 hari · <b>09.00–17.00 WIB</b><br>Kelompok 1: Penjualan & Retur<br>Kelompok 2: Hulu, Pengadaan & Sample</div>
<div><span class="lbl">Kandidat uji</span>VPS UAT setelah <b>update.sh</b><br>kode <b>main</b> terbaru (≥ c8f7f30)</div>
<div><span class="lbl">Dokumen</span>{DOC_ID} · versi 3.0<br>{DATE}</div>
<div><span class="lbl">Disusun</span>Production IT</div>
</div></section>"""


def how_to():
    return f"""<section class="sec">{head("Cara memakai", "Cara membaca & menjalankan dokumen ini", ["Baca 5 menit sebelum mulai"])}
<div class="strip c2">
<div class="box"><b class="t">Langkah kerja penguji</b><ol class="big" style="margin:0;padding-left:4mm">
<li>Buka halaman alur kelompok Anda (lihat <b>Jadwal</b>). Kerjakan baris <b>dari atas ke bawah</b>.</li>
<li>Kolom <b>Peran · akun</b> menunjukkan siapa yang mengerjakan baris itu dan perangkatnya: <b>Sales memakai HP</b> (aplikasi HP tampil otomatis di layar HP); peran lain memakai <b>desktop</b>. Ganti pengguna = <b>Keluar</b> lalu masuk dengan akun peran tersebut.</li>
<li>Kolom <b>Buka</b> menulis jalurnya: <span class="nav">menu › antrean</span> lalu tombol <span class="btn">Tombol</span> yang diklik.</li>
<li>Bandingkan layar dengan kolom <b>Hasil yang harus terlihat</b>. Sama → centang <b>Lulus</b>; berbeda / tombol tidak ada → <b>Gagal</b> + catat di lembar temuan.</li>
<li>Tulis nomor dokumen yang muncul (SO, SJ, LG, AR, …) di kolom <b>No. dok</b> — langkah berikutnya mencari dokumen itu.</li>
</ol></div>
<div class="box a"><b class="t">Tips layar yang sering ditanyakan</b><ul class="big">
<li>Akun Finance / Admin Gudang / Admin masuk sebagai <b>Semua Entitas</b> (hanya melihat). Sebelum membuat dokumen klik <b>Kerja di: Sukacita</b> (atau PT yang dipakai alur) di banner atas.</li>
<li>Mencari dokumen di antrean meja: ketik nomor SO/SJ di <b>kolom cari</b> di atas antrean.</li>
<li>Gudang tanpa tag RFID: ambil roll tetap bisa (scan/ketik nomor roll atau <span class="btn">Ambil</span>). Saat <b>kirim</b> ditolak <i>roll belum bertag RFID aktif</i> → Admin Gudang mengisi alasan lalu <span class="btn">Override</span> di <i>Pemeriksaan Muat Akhir</i>, kirim lanjut.</li>
<li>Roll hasil potong: potong & verifikasi label di <span class="nav">Lokasi Rak › Antrean Potong</span> (scan/ketik nomor label roll anak) — tidak perlu RFID.</li>
<li>Sandi akun demo dibagikan fasilitator; semua akun peran memakai sandi yang sama.</li>
</ul></div></div>
<div class="strip c3">
<div class="box g"><b class="t">Arti kolom “Cek UI”</b><ul><li><span class="t-ok">✓ dicek di layar (S1/S2)</span> — tim IT sudah menjalankan langkah ini di layar dengan akun peran yang sama (21–22 Okt 2026) dan tombolnya ada.</li>
<li><span class="t-na">○ belum dicek di layar</span> — sudah diuji di sisi sistem, tetapi belum dijalankan lewat layar. Perhatikan khusus: bila tombol/menu tidak ada, itu temuan.</li></ul></div>
<div class="box"><b class="t">Status hasil</b><ul><li><b>Lulus</b> — hasil sama dengan kolom “harus terlihat”.</li><li><b>Gagal</b> — berbeda, error, atau tombol tidak ada.</li><li><b>Terblokir</b> — tidak bisa dicoba karena langkah sebelumnya gagal / data tidak ada.</li></ul></div>
<div class="box r"><b class="t">Jangan</b><ul><li>Memakai akun Admin untuk menjalankan langkah peran lain.</li><li>Melompati baris — tiap baris menyiapkan baris berikutnya.</li><li>Menganggap lulus tanpa melihat hasil di layar.</li></ul></div>
</div></section>"""


def overview(pages):
    rows = []
    for sc in V.SCENARIOS:
        code, title, when, grp, start, mins, roles, data, fixes, ui, fn = sc
        n = len(fn())
        k, label = UI_FULL[ui]
        pg = pages.get(f"{code} — {title}", "")
        mark = {"full": '<span class="t-ok">✓ semua langkah</span>', "partial": '<span class="t-warn">◐ sebagian</span>',
                "none": '<span class="t-na">○ belum</span>'}[ui]
        rows.append(f'<tr class="grp{grp}"><td class="no">{code}</td><td><b>{escape(title)}</b> — <span class="small">{escape(when)}</span></td>'
                    f"<td>K{grp} · <b>{start}–{_end(start, mins)}</b></td><td class='small'>{escape(roles)}</td>"
                    f"<td>{n}</td><td>{mark}</td><td class='small'>{escape(fixes)}</td><td>{pg}</td></tr>")
    return f"""<section class="sec">{head("Daftar alur", "Daftar 16 alur uji", ["Biru = Kelompok 1 (K1)", "Oranye = Kelompok 2 (K2)"])}
<table class="grid compact"><colgroup><col style="width:4%"><col style="width:42%"><col style="width:10%"><col style="width:20%"><col style="width:5%"><col style="width:10%"><col style="width:6%"><col style="width:3%"></colgroup>
<thead><tr><th>Kode</th><th>Alur & kapan cabang ini terjadi</th><th>Kelompok · jam</th><th>Peran yang terlibat</th><th>Langkah</th><th>Cek UI</th><th>Perbaikan terkait</th><th>Hal.</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
<p class="small" style="margin-top:2mm">Perbaikan terkait = kode temuan pra-UAT yang sudah diperbaiki; perhatikan langkah terkait.</p></section>"""


def schedule():
    def table(grp):
        rows = [("09.00", "09.15", "Pembukaan: login semua akun peran, pilih <b>Kerja di</b>, bagikan lembar hasil", "Fasilitator · semua peran")]
        for sc in V.SCENARIOS:
            code, title, when, g, start, mins, roles, data, fixes, ui, fn = sc
            if g == grp:
                rows.append((start, _end(start, mins), f"<b>{code}</b> · {escape(title)}<br><span class='small'>Data: {escape(data)}</span>", escape(roles)))
        rows.append(("12.20", "13.20", "<i>Istirahat, sholat, makan</i>", ""))
        if grp == 1:
            rows.append(("14.50", "15.05", "<i>Rehat</i>", ""))
        rows.append(("16.30", "17.00", "Rekap: hitung Lulus/Gagal/Terblokir, bacakan temuan, putuskan tindak lanjut", "Fasilitator · pemilik proses · IT"))
        rows.sort(key=lambda r: r[0])
        body = "".join(f"<tr><td class='time'>{a}–{b}</td><td>{c}</td><td class='small'>{d}</td></tr>" for a, b, c, d in rows)
        return (f'<h3>{GROUP[grp]}</h3><table class="grid sched compact"><colgroup><col style="width:13%"><col style="width:55%"><col style="width:32%"></colgroup>'
                f"<thead><tr><th>Jam</th><th>Alur</th><th>Peran</th></tr></thead><tbody>{body}</tbody></table>")
    return f"""<section class="sec">{head("Jadwal", "Jadwal 1 hari — mulai 09.00 WIB, dua kelompok berjalan bersamaan", ["09.00–17.00 WIB", "Persiapan tim IT selesai sebelum 09.00"])}
<div class="strip c2" style="align-items:start"><div>{table(1)}</div><div>{table(2)}</div></div>
<div class="strip c4">
<div class="box"><b class="t">Pembagian kelompok</b><ul><li>Kelompok 1: penjualan & retur.</li><li>Kelompok 2: pembelian, makloon, multi-gudang, sample & Pesanan Khusus.</li></ul></div>
<div class="box a"><b class="t">Peran yang dipakai dua kelompok</b><ul><li>Admin Gudang, Gudang, Finance, Manajer, QC dipakai keduanya: siapkan satu orang per kelompok, atau satu orang bergantian dengan dua perangkat.</li><li>Bila peserta tidak cukup: kerjakan Kelompok 1 lebih dulu, alur Kelompok 2 yang belum selesai dijadwalkan ulang.</li></ul></div>
<div class="box r"><b class="t">Persiapan IT sebelum 09.00</b><ul><li><code>update.sh</code> di VPS → commit terbaru.</li><li>Admin: <b>Pusat Pengaturan › Stok & Satuan › Mode simulasi RFID</b> = Ya untuk Sukacita, Kanda Fabric, Cipta Sandang (UAT tanpa handheld/tag). Matikan lagi setelah UAT.</li><li>S9: <b>Pembelian › Master Pembelian › Resep Proses</b> untuk artikel makloon contoh (RIVERA RIB) bila belum ada.</li><li>Semua akun demo: sandi sama (lihat lembar akun).</li></ul></div>
<div class="box g"><b class="t">Ketergantungan</b><ul><li>S14 & S15 (retur) memakai SO dari S1 yang sudah <i>Selesai</i>.</li><li>S8, S9, S16 menunggu barang supplier/mitra “di luar sistem” — fasilitator memerankan supplier (SJ contoh).</li></ul></div>
</div></section>"""


def scenario_page(sc):
    code, title, when, grp, start, mins, roles, data, fixes, ui, fn = sc
    rows = fn()
    k, label = UI_FULL[ui]
    chips = [GROUP[grp].split(" · ")[0] + f" · {start}–{_end(start, mins)}", (k, label)]
    if fixes and fixes != "—":
        chips.append(("a", "Perbaikan: " + fixes))
    lead = (f"<p class='lead'><b>Kapan:</b> {fmt(when)}<br><b>Peran:</b> {escape(roles)} · <b>Data:</b> {escape(data)}</p>")
    return "\n".join(['<section class="sec">', head(f"Alur {code} · {len(rows)} langkah", f"{code} — {title}", chips), lead,
                      '<h3 style="margin:1mm 0 1mm 0">Diagram alur</h3>', FLOW.swimlane(code, rows),
                      '<h3 style="margin:2mm 0 0 0">Navigasi menu per tahap</h3>', VIS.flow_strip(code, rows),
                      steps_table(code, rows), "</section>"])


def data_page():
    fx = "".join(f"<tr><td class='no'>{a}</td><td><b>{escape(b)}</b></td><td>{fmt(c)}</td></tr>" for a, b, c, d in sched.FIX)
    acc = "".join(f"<tr><td><b>{escape(a)}</b></td><td class='small'>{escape(b)}</td><td>{escape(c)}</td></tr>" for a, b, c, d in sched.ACC)
    cf = "".join(f"<tr><td>{escape(a)}</td><td>{fmt(b)}</td><td>{escape(c)}</td></tr>" for a, b, c, d in sched.CFG)
    return f"""<section class="sec">{head("Data uji", "Data acuan, akun per peran & pengaturan yang mempengaruhi hasil", ["Sandi dibagikan fasilitator"])}
<div class="strip c2" style="grid-template-columns: 1.1fr 1fr; align-items:start">
<div><h3 style="margin-top:0">Data acuan</h3><table class="grid"><colgroup><col style="width:9%"><col style="width:22%"><col style="width:69%"></colgroup>
<thead><tr><th>Kode</th><th>Data</th><th>Isi / patokan</th></tr></thead><tbody>{fx}</tbody></table>
<h3>Pengaturan (catat nilai aktual di VPS sebelum mulai)</h3><table class="grid"><colgroup><col style="width:34%"><col style="width:36%"><col style="width:30%"></colgroup>
<thead><tr><th>Pengaturan</th><th>Kunci / lokasi</th><th>Nilai acuan</th></tr></thead><tbody>{cf}
<tr><td>Tahan kirim CBD/DP sampai dibayar</td><td>{fmt("`finance.dispatch_payment_gate`")}</td><td>Blok keras (bawaan)</td></tr>
<tr><td>Toleransi harga sample berbayar</td><td>{fmt("`sales.sample_payment_tolerance_pct`")}</td><td>±5%</td></tr></tbody></table></div>
<div><h3 style="margin-top:0">Akun per peran</h3><table class="grid"><colgroup><col style="width:26%"><col style="width:38%"><col style="width:36%"></colgroup>
<thead><tr><th>Peran</th><th>Akun</th><th>Pintu kerja</th></tr></thead><tbody>{acc}
<tr><td><b>Admin Sample</b></td><td class='small'>sampleadmin@kainnusantara.id</td><td>Meja Sample · Pesanan Sample</td></tr></tbody></table></div>
</div></section>"""


def closing():
    rows = "".join(f"<tr class='grp{sc[3]}'><td class='no'>{sc[0]}</td><td>{escape(sc[1])}</td><td></td><td></td><td></td><td></td><td></td></tr>"
                   for sc in V.SCENARIOS)
    form = "".join(f"<tr><td><b>{x}</b></td><td></td></tr>" for x in (
        "ID temuan / langkah (mis. S4-07)", "Akun / peran / badan usaha", "Nomor dokumen / roll", "Yang dilakukan",
        "Yang seharusnya terlihat", "Yang terjadi (tangkapan layar)", "Bug / keputusan bisnis / data", "Prioritas · PIC · target"))
    return f"""<section class="sec">{head("Penutupan", "Rekap hasil per alur, form temuan & persetujuan", ["Diisi pencatat pukul 16.30"])}
<div class="strip c2" style="grid-template-columns: 1.25fr 1fr; align-items:start">
<div><table class="grid"><colgroup><col style="width:7%"><col style="width:45%"><col style="width:9%"><col style="width:9%"><col style="width:10%"><col style="width:9%"><col style="width:11%"></colgroup>
<thead><tr><th>Alur</th><th>Judul</th><th>Lulus</th><th>Gagal</th><th>Terblokir</th><th>Siap?</th><th>ID temuan</th></tr></thead><tbody>{rows}</tbody></table></div>
<div><h3 style="margin-top:0">Form satu temuan</h3><table class="grid"><colgroup><col style="width:42%"><col style="width:58%"></colgroup><tbody>{form}</tbody></table>
<div class="box a" style="margin-top:2mm"><b class="t">Aturan temuan</b><ul><li>Catat ≤ 5 menit setelah terjadi, lengkap dengan nomor langkah.</li>
<li>Pisahkan: <b>bug</b> (sistem salah) · <b>keputusan bisnis</b> (aturan belum disepakati) · <b>data</b> (data uji tidak sesuai).</li></ul></div></div></div>
<div class="sign"><div>Pemilik proses / client</div><div>Production IT</div><div>Fasilitator</div><div>Pencatat</div></div></section>"""


def all_sections(pages):
    menus = FLOW.nav_pages(V.SCENARIOS,
                           head("Navigasi · Sales", "Navigasi menu Sales — aplikasi HP", ["Sales memakai HP"]),
                           head("Navigasi · Desktop", "Navigasi menu peran lain — desktop", ["Admin Sales, Manajer, Finance, Gudang, QC, MD, Desainer, Admin Sample"]))
    return [cover(), how_to(), overview(pages), schedule(), menus] + [scenario_page(sc) for sc in V.SCENARIOS] + [data_page(), closing()]


def build_html(pages):
    return (f'<!doctype html><html lang="id"><head><meta charset="utf-8"><title>Panduan UAT End-to-End — ERP Kain Nusantara v3.0</title>'
            f'<style>{CSS}</style></head><body>{"".join(all_sections(pages))}</body></html>')


def find_pages(pdf):
    """pagefind.py (milik v2) menulis toc_titles/toc_pages.json — isi v2 dipulihkan sesudahnya."""
    keep = {n: (open(os.path.join(HERE, n), encoding="utf-8").read() if os.path.exists(os.path.join(HERE, n)) else None)
            for n in ("toc_titles.json", "toc_pages.json")}
    titles = [f"{sc[0]} — {sc[1]}" for sc in V.SCENARIOS]
    json.dump(titles, open(os.path.join(HERE, "toc_titles.json"), "w", encoding="utf-8", newline="\n"), ensure_ascii=False)
    rel = os.path.relpath(pdf, os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))).replace("\\", "/")
    env = dict(os.environ, MSYS_NO_PATHCONV="1")
    r = subprocess.run(["docker", "exec", os.environ.get("KN_PAGEFIND_CONTAINER", "kn-verify-backend"), "python",
                        "/app/docs/uat/2026-10-21/src/pagefind.py", "/app/" + rel], capture_output=True, text=True, env=env)
    print(r.stdout.strip() or r.stderr.strip()[:300])
    src = os.path.join(HERE, "toc_pages.json")
    if r.returncode == 0 and os.path.exists(src):
        open(PAGES_JSON, "w", encoding="utf-8", newline="\n").write(open(src, encoding="utf-8").read())
    for n, txt in keep.items():
        f = os.path.join(HERE, n)
        if txt is None:
            if os.path.exists(f):
                os.remove(f)
        else:
            open(f, "w", encoding="utf-8", newline="\n").write(txt)


def result_sheet():
    def plain(x):
        x = re.sub(r"\[\[([^\]]+)\]\]", r"[\1]", x)
        return x.replace("**", "").replace("`", "").replace("*", "").replace("|", "/")
    md = ["# Lembar hasil UAT — ERP Kain Nusantara (KN-UAT-E2E-003 v3.0)", "",
          "**Tanggal:** ______ (09.00–17.00 WIB)  **Kandidat:** VPS setelah update.sh · commit ______  **Fasilitator:** ______  **Pencatat:** ______", "",
          "Status: `L` Lulus · `G` Gagal · `T` Terblokir. Isi nomor dokumen sistem & ID temuan.", ""]
    for code, title, when, grp, start, mins, roles, data, fixes, ui, fn in V.SCENARIOS:
        md += [f"## {code} — {title} ({GROUP[grp]}, {start}–{_end(start, mins)})", "",
               "| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |", "|---|---|---|---|---|---|---|"]
        for i, (role, nav, act, exp, u) in enumerate(fn(), 1):
            r = role[0] if isinstance(role, tuple) else role
            e = plain(exp)
            md.append(f"| {code}-{i:02d} | {r} | {e[:150] + ('…' if len(e) > 150 else '')} | {'✓ ' + u if u else '○'} |  |  |  |")
        md.append("")
    md += ["## Penutupan", "", "- Lulus ___ · Gagal ___ · Terblokir ___", "- Alur siap pakai: ___", "- Keputusan bisnis: ___",
           "- Rencana perbaikan & uji ulang: ___", "- Tanda tangan: pemilik proses ___ · Production IT ___ · fasilitator ___ · pencatat ___", ""]
    p = os.path.join(OUT_DIR, "LEMBAR_HASIL_UAT_v3.md")
    open(p, "w", encoding="utf-8", newline="\n").write("\n".join(md))
    return p


def main():
    from build import render
    hp = os.path.join(OUT_DIR, NAME + ".html")
    pdf = os.path.join(OUT_DIR, NAME + ".pdf")
    passes = 1 if "--html" in sys.argv else 2
    for k in range(passes):
        pages = json.load(open(PAGES_JSON, encoding="utf-8")) if os.path.exists(PAGES_JSON) else {}
        with open(hp, "w", encoding="utf-8", newline="\n") as f:
            f.write(build_html(pages))
        if "--html" in sys.argv:
            break
        render(hp, pdf)
        if k == 0:
            find_pages(pdf)
    print("HTML:", hp)
    if os.path.exists(pdf):
        print("PDF :", pdf, os.path.getsize(pdf), "bytes")
    print("Lembar:", result_sheet())
    print("langkah:", sum(len(sc[-1]()) for sc in V.SCENARIOS))


if __name__ == "__main__":
    main()
