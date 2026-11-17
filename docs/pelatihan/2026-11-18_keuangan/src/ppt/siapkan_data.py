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


DOKUMEN = [   # (judul, pola gambar di uji/hasil, kata kunci baris src/dokumen_cetak.json)
    ("Faktur Komersial (faktur penjualan)", "D1/faktur-0*-1.png", "Faktur Komersial"),
    ("Konfirmasi Pesanan (SO)", "D1/pesanan-KSC-SO-*-1.png", "Konfirmasi Pesanan"),
    ("Surat Jalan", "D1/surat-jalan-*-1.png", "Surat Jalan"),
    ("Daftar Kemasan (packing list)", "D1/daftar-kemasan-*-1.png", "Daftar Kemasan"),
    ("Surat Pengambilan Barang", "D1/surat-pengambilan-*-1.png", "Surat Pengambilan"),
    ("Kwitansi penerimaan piutang", "D2/kwitansi-*-1.png", "Kwitansi"),
    ("Rekening Koran pelanggan", "D2/rekening-koran-1.png", "Rekening Koran"),
    ("Faktur Pajak Keluaran (salinan ERP)", "D2/faktur-pajak-*-1.png", "Faktur Pajak"),
    ("Pesanan Pembelian (PO)", "D2/po-*-1.png", "Pesanan Pembelian"),
    ("Tagihan Supplier", "D2/tagihan-VB-*-1.png", "Tagihan Supplier"),
    ("Tanda Terima Kontrabon", "D2/kontrabon-*-1.png", "Kontrabon"),
    ("Form Pengajuan Dana (PD) kas kecil", "D2/pd-*-1.png", "Pengajuan Dana"),
    ("Tanda Terima pencairan PD", "D2/tanda-terima-*-1.png", "Tanda Terima pencairan"),
    ("LPJ kas kecil", "D2/lpj-*-1.png", "LPJ"),
    ("Bukti Kas Keluar", "D2/bukti-kas-keluar-*-1.png", "Bukti Kas"),
    ("Bukti Kas Masuk", "D2/bukti-kas-masuk-*-1.png", "Bukti Kas"),
    ("Slip Gaji", "D2/slip-gaji-*-1.png", "Slip Gaji"),
]


def dokumen():
    import glob
    f = os.path.join(SRC, "dokumen_cetak.json")
    rows = []
    if os.path.exists(f):
        raw = json.load(open(f, encoding="utf-8"))
        rows = raw if isinstance(raw, list) else raw.get("baris") or []
    out = []
    for judul, pola, kunci in DOKUMEN:
        files = sorted(glob.glob(os.path.join(ROOT, "uji", "hasil", pola)))
        if not files:
            continue
        rel = B.opt(os.path.relpath(files[0], ROOT), 1100)
        r = next((x for x in rows if kunci.lower() in str(x.get("dokumen", "")).lower()), {})
        cara = re.sub(r"\s*[;·]?\s*(GET|POST) /api/[^;]*", "", bersih(r.get("cara_cetak"))).strip(" ;·")   # tanpa alamat API teknis
        out.append({"judul": judul, "img": rel, "wh": ukuran(rel), "cara_cetak": cara,
                    "dicek": bersih(r.get("dicek")), "hasil": r.get("hasil", ""), "catatan": bersih(r.get("catatan"))})
    return out


def main() -> None:
    sc = B.load()
    os.makedirs(os.path.join(HERE, "alur"), exist_ok=True)
    idx = B._nav_index()
    out = {"tanggal": B.DATE, "doc_id": B.DOC_ID, "menu": B.MENU, "istilah": B.ISTILAH, "kartu": B.KARTU,
           "jadwal": [], "skenario": []}
    # jadwal per bagian, dibagi ke hari berikutnya bila lewat 17.00 — sama dengan manual
    h, m = B.START
    hari, lunch, mod_now = 1, False, None
    out["jadwal"].append({"jam": "", "kode": "", "judul": "Hari 1", "menit": "", "hari": True})
    for d in sc:
        mins = int(d.get("menit") or 20)
        if (h * 60 + m + mins) > 17 * 60:
            hari += 1
            h, m, lunch = B.START[0], B.START[1], False
            out["jadwal"].append({"jam": "", "kode": "", "judul": f"Hari {hari}", "menit": "", "hari": True})
        if not lunch and h >= 12:
            out["jadwal"].append({"jam": f"{h:02d}.{m:02d}", "kode": "", "judul": "Istirahat & makan siang", "menit": 60})
            h += 1
            lunch = True
        mins = int(d.get("menit") or 20)
        out["jadwal"].append({"jam": f"{h:02d}.{m:02d}", "kode": d["_no"], "judul": bersih(d["judul"]), "menit": mins,
                              "peran": bersih(d.get("peran"))})
        m += mins
        h, m = h + m // 60, m % 60
    out["jadwal"].append({"jam": f"{h:02d}.{m:02d}", "kode": "", "judul": "Tanya jawab, evaluasi & penutupan", "menit": 30})
    out["hari"] = hari
    out["modul"] = [{"no": x["no"], "judul": x["judul"], "ringkas": x.get("ringkas", ""), "intro": x.get("intro", []),
                     "sub": [{"no": s["no"], "judul": s["judul"]} for s in x.get("sub", [])]} for x in B.KUR["modul"]]
    out["peran"] = B.KUR.get("peran", [])
    # peta alur uang
    with open(os.path.join(HERE, "alur", "peta_uang.html"), "w", encoding="utf-8") as fh:
        fh.write(svg_html(B.money_map()))
    # navigasi umum (gambar contoh)
    out["nav_contoh"] = [{"menu": v.get("menu"), "img": B.opt(v["file"], 1400)} for k, v in sorted(idx.items())
                         if v.get("role") == "finance" and k.endswith("|ar-aging|collection-worklist")][:1]
    for d in sc:
        role_key = "manager" if d.get("bagian") == "B" or d["_modul"]["no"] == "4" else "finance"
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
            "no": d["_no"], "modul": d["_modul"]["no"], "modul_judul": d["_modul"]["judul"],
            "sub_judul": (d.get("_sub") or {}).get("judul", ""),
            "konsep": [bersih(x) for x in d.get("konsep") or []],
            "jurnal_per_tahap": [{"tahap": bersih(r.get("tahap")), "dokumen": bersih(r.get("dokumen")), "jurnal": bersih(r.get("jurnal"))}
                                 for r in d.get("jurnal_per_tahap") or []],
            "titik_kontrol": [bersih(x) for x in d.get("titik_kontrol") or []],
            "kode": d["kode"], "judul": bersih(d["judul"]), "bagian": d.get("bagian", "A"), "peran": bersih(d.get("peran")),
            "menit": d.get("menit"), "tujuan": bersih(d.get("tujuan")), "kapan": bersih(d.get("kapan")),
            "data_awal": bersih(d.get("data_awal")), "alur": [{"peran": a.get("peran"), "label": a.get("label"),
                                                              "cabang": a.get("cabang")} for a in d.get("alur") or []],
            "navigasi": navs, "langkah": langkah, "cek_buku": [bersih(x) for x in d.get("cek_buku") or []],
            "kesalahan_umum": [bersih(x) for x in d.get("kesalahan_umum") or []],
            "catatan_pelatih": bersih(d.get("catatan_pelatih")),
            "uji": {"ok": bool(u.get("ok")), "lulus": sum(1 for s in u.get("steps", []) if s.get("ok")),
                    "langkah": len(u.get("steps", []))}})
    out["dokumen"] = dokumen()
    with open(os.path.join(HERE, "data.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    n = sum(len(s["langkah"]) for s in out["skenario"])
    print(f"data.json: {len(out['skenario'])} skenario · {n} langkah · "
          f"{sum(1 for s in out['skenario'] for x in s['langkah'] if x['img'])} bergambar")


if __name__ == "__main__":
    main()
