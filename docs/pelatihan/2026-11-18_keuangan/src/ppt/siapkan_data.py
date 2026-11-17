"""Siapkan data deck PowerPoint pelatihan dari sumber yang sama dengan manual (src/skenario/*.json + gambar uji jalan).

Keluaran: src/ppt/data.json (dibaca buat_ppt.js) + src/ppt/alur/*.html (diagram alur, dirender jadi PNG oleh render_alur.js).
    python docs/pelatihan/2026-11-18_keuangan/src/ppt/siapkan_data.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(SRC, ".."))
sys.path.insert(0, SRC)

import bangun as B  # noqa: E402

from PIL import Image  # noqa: E402


def bersih(s) -> str:
    """Teks polos untuk slide: [[Tombol]] → «Tombol», *Isian* → Isian, `menu` → menu."""
    s = str(s or "")
    s = re.sub(r"\[\[(.+?)\]\]", r"[\1]", s)
    s = re.sub(r"\*(.+?)\*", r"\1", s)
    s = re.sub(r"`(.+?)`", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def ukuran(rel: str):
    p = os.path.join(ROOT, rel)
    with Image.open(p) as im:
        return im.width, im.height


def judul_langkah(aksi: str) -> str:
    """Label pendek langkah untuk judul slide (≤ 64 huruf, potong di batas klausa)."""
    t = bersih(aksi)
    for sep in (" → ", "; ", " — ", ". ", ", lalu ", " lalu "):
        if sep in t and 12 <= t.index(sep) <= 64:
            t = t[: t.index(sep)]
            break
    if len(t) > 64:
        t = t[:61].rsplit(" ", 1)[0] + "…"
    return t


def svg_html(svg: str) -> str:
    return ("<!doctype html><html><head><meta charset='utf-8'><style>html,body{margin:0;background:#fff}"
            "#d{width:1500px;padding:8px}</style></head><body><div id='d'>" + svg + "</div></body></html>")


def main() -> None:
    sc = B.load()
    os.makedirs(os.path.join(HERE, "alur"), exist_ok=True)
    idx = B._nav_index()
    out = {"tanggal": B.DATE, "doc_id": B.DOC_ID, "menu": B.MENU, "istilah": B.ISTILAH, "kartu": B.KARTU,
           "jadwal": [], "skenario": []}
    # jadwal (jam mulai per skenario) — sama dengan manual
    h, m = B.START
    lunch = False
    for d in sc:
        if not lunch and h >= 12:
            out["jadwal"].append({"jam": f"{h:02d}.{m:02d}", "kode": "", "judul": "Istirahat & makan siang", "menit": 60})
            h += 1
            lunch = True
        mins = int(d.get("menit") or 20)
        out["jadwal"].append({"jam": f"{h:02d}.{m:02d}", "kode": d["kode"], "judul": bersih(d["judul"]), "menit": mins,
                              "peran": bersih(d.get("peran"))})
        m += mins
        h, m = h + m // 60, m % 60
    out["jadwal"].append({"jam": f"{h:02d}.{m:02d}", "kode": "", "judul": "Tanya jawab, evaluasi & penutupan", "menit": 30})
    # peta alur uang
    with open(os.path.join(HERE, "alur", "peta_uang.html"), "w", encoding="utf-8") as fh:
        fh.write(svg_html(B.money_map()))
    # navigasi umum (gambar contoh)
    out["nav_contoh"] = [{"menu": v.get("menu"), "img": B.opt(v["file"], 1400)} for k, v in sorted(idx.items())
                         if v.get("role") == "finance" and k.endswith("|ar-aging|collection-worklist")][:1]
    for d in sc:
        role_key = "manager" if d.get("bagian") == "B" else "finance"
        if d.get("alur"):
            with open(os.path.join(HERE, "alur", f"{d['kode']}.html"), "w", encoding="utf-8") as fh:
                fh.write(svg_html(B.flow_svg(d["alur"])))
        navs = []
        for n in d.get("navigasi") or []:
            hit = idx.get(f"{role_key}|{n.get('nav_id')}|{n.get('tab') or ''}") or next(
                (v for k, v in idx.items() if k.endswith(f"|{n.get('nav_id')}|{n.get('tab') or ''}")), None)
            rel = B.opt(hit["file"], 1400) if hit and os.path.exists(os.path.join(ROOT, hit["file"])) else ""
            navs.append({"menu": bersih(n.get("menu")), "img": rel, "wh": ukuran(rel) if rel else None})
        langkah = []
        for s in d.get("langkah") or []:
            rel = B.opt(s.get("gambar"), 1400) if s.get("gambar") else ""
            langkah.append({"no": s.get("no"), "peran": bersih(s.get("peran")), "menu": bersih(s.get("menu")),
                            "judul": judul_langkah(s.get("aksi")), "aksi": bersih(s.get("aksi")), "isi": bersih(s.get("isi")),
                            "hasil": bersih(s.get("hasil")), "img": rel, "wh": ukuran(rel) if rel else None})
        u = d.get("_uji") or {}
        out["skenario"].append({
            "kode": d["kode"], "judul": bersih(d["judul"]), "bagian": d.get("bagian", "A"), "peran": bersih(d.get("peran")),
            "menit": d.get("menit"), "tujuan": bersih(d.get("tujuan")), "kapan": bersih(d.get("kapan")),
            "data_awal": bersih(d.get("data_awal")), "alur": [{"peran": a.get("peran"), "label": a.get("label"),
                                                              "cabang": a.get("cabang")} for a in d.get("alur") or []],
            "navigasi": navs, "langkah": langkah, "cek_buku": [bersih(x) for x in d.get("cek_buku") or []],
            "kesalahan_umum": [bersih(x) for x in d.get("kesalahan_umum") or []],
            "catatan_pelatih": bersih(d.get("catatan_pelatih")),
            "uji": {"ok": bool(u.get("ok")), "lulus": sum(1 for s in u.get("steps", []) if s.get("ok")),
                    "langkah": len(u.get("steps", []))}})
    with open(os.path.join(HERE, "data.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    n = sum(len(s["langkah"]) for s in out["skenario"])
    print(f"data.json: {len(out['skenario'])} skenario · {n} langkah · "
          f"{sum(1 for s in out['skenario'] for x in s['langkah'] if x['img'])} bergambar")


if __name__ == "__main__":
    main()
