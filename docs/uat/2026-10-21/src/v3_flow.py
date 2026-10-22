"""UAT v3.0 — diagram alur swimlane per skenario + halaman panduan navigasi (HP Sales & desktop per peran).

Diagram diturunkan dari langkah (satu kotak = langkah berurutan oleh peran yang sama), jadi selalu sama dengan tabel.
Menu kiri per peran diambil dari konfigurasi menu aplikasi (`v3_nav.json`, hasil buildNavGroups di frontend).
"""
import json
import os
import re
from html import escape

import diagram as DG
from page import ROLE_COLORS, fmt
from v3_visual import DEVICE, _buttons, _menus, phone_mock, role_menus, stages

HERE = os.path.dirname(os.path.abspath(__file__))


def _color(role):
    return ROLE_COLORS.get(role.split(" ·")[0].split(" (")[0].split(" /")[0], "#334155")


def _stage_text(st):
    menus = " → ".join(m.replace("HP › ", "") for m in _menus(st["navs"])) or "layar yang sama"
    btns = _buttons(st["navs"], 12)
    chain = f"{btns[0]} … {btns[-1]}" if len(btns) > 2 else " → ".join(btns)
    return menus + ("\n" + chain if chain else "")


def swimlane(code, rows, maxcols=7):
    sts = stages(rows)
    chunks = [sts[i:i + maxcols] for i in range(0, len(sts), maxcols)]
    out = []
    for ci, ch in enumerate(chunks):
        roles = []
        for st in ch:
            if st["role"] not in roles:
                roles.append(st["role"])
        lanes, key = [], {}
        for r in roles:
            k = "v3_" + re.sub(r"\W+", "_", r.lower())
            dev = DEVICE.get(r, ("Desktop", ""))[0]
            DG.ROLE[k] = (f"{r} ({dev})", _color(r))
            lanes.append((k, f"{r} ({dev})"))
            key[r] = k
        last = ci == len(chunks) - 1
        d = DG.Diagram(lanes, len(ch) + 1 + (1 if last else 0), lane_h=54, label_w=104)
        prev = d.n("start", key[ch[0]["role"]], 0, "start" if ci == 0 else "link", "Mulai" if ci == 0 else "▶")
        col = 1
        for st in ch:
            nid = f"s{st['from']}"
            num = f"{code}-{st['from']:02d}" + (f"…{st['to']:02d}" if st["to"] != st["from"] else "")
            d.n(nid, key[st["role"]], col, "task", _stage_text(st), num=num, fs=7.6)
            d.e(prev, nid)
            prev, col = nid, col + 1
        if last:
            d.n("end", key[ch[-1]["role"]], col, "end", "Selesai")
            d.e(prev, "end")
        out.append(d.render())
        if not last:
            out.append('<p class="small" style="margin:.5mm 0 1.2mm 0">▶ berlanjut ke baris diagram berikutnya</p>')
    return "".join(out)


ROLE_IDS = [("Admin Sales", "sales_admin", "salesadmin@kainnusantara.id"), ("Manajer", "manager", "manager@kainnusantara.id"),
            ("Finance", "finance", "finance@kainnusantara.id"), ("Gudang", "warehouse", "warehouse@kainnusantara.id"),
            ("Admin Gudang", "warehouse_admin", "wh.admin@kainnusantara.id"), ("QC", "qc", "qc@kainnusantara.id"),
            ("MD Quality", "md_quality", "mdquality@kainnusantara.id"), ("MD", "md", "md@kainnusantara.id"),
            ("Desainer", "designer", "designer@kainnusantara.id"), ("Admin Sample", "sample_admin", "sampleadmin@kainnusantara.id"),
            ("Pembelian", "manager", "manager@kainnusantara.id"),
            ("R&D", "md", "md@kainnusantara.id"), ("CST", "sales_admin", "salesadmin.cst@kainnusantara.id")]
HOME_LABEL = {"sales-admin-desk": "Meja Admin Sales", "manager-home": "Beranda Manajer", "finance-desk": "Meja Finance",
              "operations": "Operasi Gudang", "warehouse-admin-desk": "Meja Gudang", "inspections": "QC & Inspeksi (SPK Inspeksi)",
              "md-desk": "Meja MD", "design-requests": "Permintaan Desain", "sample-admin-desk": "Meja Sample"}

SALES_TASKS = [
    ("Membuat pesanan", "tab **Katalog** → bilah **Pelanggan** (atas) → pilih pelanggan → cari → kartu produk (stok PT penjual · grup) [[Tambah]] (artikel bervarian: [[Pilih]]) → warna, *Order biasa*, qty → [[Tambah …]] → Genapkan → tab **Keranjang** → "
                        "[[Lanjut ke Checkout]] → 3 langkah → [[Buat Sales Order]]"),
    ("Melihat status & perjalanan pesanan", "tab **Pesanan** → cari nomor / pelanggan → ketuk kartu SO → bagian *Perjalanan Pesanan*"),
    ("Minta harga khusus untuk pesanan ini", "Checkout langkah 2 → kartu item [[Minta Harga Khusus]] → harga + alasan → [[Simpan]]; SO lahir "
     "harga normal, ACC Manajer → harga baru & dilepas ke gudang otomatis. Ditolak → tab **Pesanan** → ketuk SO → kotak *Persetujuan*: "
     "[[Ajukan harga lain]] / [[Lanjut harga normal]] / [[Batalkan pesanan]]"),
    ("Harga langganan (pesanan berikutnya)", "**Lainnya** › *Minta Harga Khusus* → pelanggan, produk, harga + bukti → [[Ajukan]] (opsional *Berlaku sampai*); "
     "setelah ACC Manajer harga otomatis muncul di katalog, keranjang & checkout (*Harga khusus*)"),
    ("Izin kredit (pelanggan terblokir)", "bilah **Pelanggan** → kotak merah *Pelanggan ini tidak bisa membeli* → "
     "[[Ajukan Override Kredit (Rp …)]] + alasan → [[Ajukan]]; checkout terbuka lagi sesudah ACC Manajer"),
    ("Koreksi qty / harga", "tab **Pesanan** → ketuk SO → [[Ajukan koreksi]] (atau **Lainnya** › *Koreksi & Amandemen*)"),
    ("Catat pembayaran di lapangan", "tab **Pesanan** → ketuk SO → [[Catat bayar]]"),
    ("Pesanan sample", "tab **Katalog** → kartu produk [[Tambah]] (artikel bervarian: [[Pilih]]) → *Order sample* → Keranjang → Checkout (Gratis / Berbayar); status di **Lainnya** › *Pesanan Sample*"),
    ("Pesanan Khusus (OD)", "tab **Lainnya** › *Pesanan Khusus (OD)* → [[Ajukan pesanan khusus]] → formulir 6 bagian → [[Simpan pesanan khusus]]; sample jadi → ketuk OD → *Persetujuan pelanggan atas sample* → [[ACC]] + bukti → [[Simpan keputusan]]"),
    ("Retur pelanggan", "tab **Pesanan** → ketuk SO yang sudah dikirim → [[Ajukan retur]] (atau **Lainnya** › *Retur Penjualan* → [[Buat retur jual]])"),
    ("Ganti PT / keluar", "tab **Lainnya** → *Badan usaha aktif* (bila punya lebih dari 1 PT) · [[Keluar]] di bagian bawah"),
]


def _nav():
    return json.load(open(os.path.join(HERE, "v3_nav.json"), encoding="utf-8"))


def _locate(groups, menu):
    """Jalur menu kiri lengkap untuk satu menu yang dipakai di langkah (mis. 'Operasi Gudang › Barang Keluar')."""
    segs = [s.strip() for s in menu.split("›")]
    first, rest = segs[0], segs[1:]
    if rest and any("group" in g and g["group"].lower() == first.lower() for g in groups):
        return _locate(groups, " › ".join(rest))     # langkah menulis nama kelompok (mis. "Pembelian › Hutang Pemasok")
    for g in groups:
        entries = g["items"] if "group" in g else [g]
        for i in entries:
            pre = [g["group"].upper()] if "group" in g else []
            if i["label"] == first:
                tab = [f"tab {rest[0]}"] if rest and rest[0] in (i.get("tabs") or []) else rest
                return " › ".join(pre + [i["label"]] + tab), True
            if first in (i.get("tabs") or []):
                return " › ".join(pre + [i["label"], f"tab {first}"] + rest), True
    return menu, False


def _sidebar(groups, used):
    lines = []
    for g in groups:
        entries = g["items"] if "group" in g else [g]
        parts = []
        for i in entries:
            lab = i["label"] + (f" ({', '.join(i['tabs'])})" if i.get("tabs") and len(i["tabs"]) <= 5 else "")
            hit = any(i["label"] in u for u in used)
            parts.append(f"<b>{escape(lab)}</b>" if hit else escape(lab))
        prefix = f"<span style='color:#64748B'>{escape(g['group'].upper())} ›</span> " if "group" in g else ""
        lines.append(prefix + " · ".join(parts))
    return "<br>".join(lines)


def nav_pages(scenarios, head_sales, head_desk):
    trs = "".join(f"<tr><td><b>{escape(a)}</b></td><td>{fmt(b)}</td></tr>" for a, b in SALES_TASKS)
    p1 = (f'<section class="sec">{head_sales}<div class="menumap"><div>{phone_mock()}</div><div>'
          '<div class="box" style="margin-bottom:2mm"><b class="t">Membuka aplikasi HP</b><ul>'
          '<li>Di HP buka alamat UAT (dari fasilitator) di Chrome → masuk dengan akun <b>sales@kainnusantara.id</b>.</li>'
          '<li>Aplikasi HP tampil otomatis: bilah atas (nama, PT aktif, lonceng) dan <b>5 tab di bawah</b>: '
          'Beranda · Katalog · Keranjang · Pesanan · Lainnya.</li>'
          '<li>Jangan memakai <i>Lainnya › Tampilan Desktop</i> saat UAT (itu tampilan komputer).</li></ul></div>'
          '<table class="grid"><colgroup><col style="width:28%"><col style="width:72%"></colgroup>'
          f'<thead><tr><th>Yang ingin dilakukan Sales</th><th>Navigasi di HP</th></tr></thead><tbody>{trs}</tbody></table>'
          '</div></div></section>')
    nav = _nav()
    rm = role_menus(scenarios)
    rows = []
    for label, rid, acct in ROLE_IDS:
        v = nav.get(rid) or {}
        used = rm.get(label) or {}
        home = HOME_LABEL.get((v.get("home") or {}).get("view") or "", "Beranda")
        paths = {}
        for m, codes in used.items():
            path, found = _locate(v.get("groups") or [], m)
            if not found and any(seg.strip() and home.startswith(seg.strip()) for seg in m.split("›")):
                path = f"{home} (halaman pertama)"
            paths.setdefault(path, [])
            paths[path] += [c for c in codes if c not in paths[path]]
        lines = "".join(f'<div style="margin-bottom:.4mm">{fmt("`" + p + "`")} <span class="small">{" ".join(c)}</span></div>'
                        for p, c in sorted(paths.items(), key=lambda kv: -len(kv[1])))
        rows.append(f'<tr><td><span class="role" style="background:{_color(label)}">{escape(label)}</span>'
                    f'<span class="acct">{escape(acct)}</span></td><td><b>{escape(home)}</b></td><td>{lines or "—"}</td></tr>')
    p2 = (f'<section class="sec">{head_desk}<div class="strip c3" style="margin-top:0">'
          '<div class="box"><b class="t">Bagian layar desktop</b><ul>'
          '<li><b>Menu kiri</b>: KERJA SAYA (Beranda, Meja …) lalu MODUL per kelompok — klik kelompok untuk membuka isinya.</li>'
          '<li><b>Bilah atas</b>: jalur halaman, <b>Kerja di: &lt;PT&gt;</b>, lonceng notifikasi.</li>'
          '<li><b>Cari menu… (Ctrl+K)</b>: ketik nama menu untuk langsung membuka.</li></ul></div>'
          '<div class="box a"><b class="t">Kartu antrean di Meja</b><ul><li>Judul antrean · jumlah · umur tertua · nilai.</li>'
          '<li>Ketik nomor SO/SJ di <b>kolom cari</b>, atau <span class="btn">Sebelumnya</span> / <span class="btn">Berikutnya</span>.</li>'
          '<li>Tiap baris punya satu tombol aksi (mis. <span class="btn">Periksa &amp; lepas</span>, <span class="btn">Catat kwitansi</span>).</li></ul></div>'
          '<div class="box g"><b class="t">Ganti peran</b><ul><li>Klik <b>Keluar</b> (kiri bawah) → masuk dengan akun peran berikutnya.</li>'
          '<li>Akun Finance / Admin Gudang mulai di <i>Semua Entitas</i>: klik <b>Kerja di: Sukacita</b> sebelum membuat dokumen.</li></ul></div></div>'
          '<table class="grid compact"><colgroup><col style="width:15%"><col style="width:13%"><col style="width:72%"></colgroup>'
          '<thead><tr><th>Peran · akun</th><th>Halaman pertama setelah masuk</th><th>Jalur menu kiri yang dipakai di UAT · alur</th></tr></thead>'
          f'<tbody>{"".join(rows)}</tbody></table></section>')
    return p1 + p2
