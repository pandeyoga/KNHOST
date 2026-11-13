#!/usr/bin/env python3
"""Hitung pendaftaran temuan paket 2026-11-13 di tracker. Baca-saja kecuali dengan --bangun.

    python docs/reviews/2026-11-13/garis-dasar/hitung_tracker.py            # periksa; kode 1 bila ada selisih
    python docs/reviews/2026-11-13/garis-dasar/hitung_tracker.py --bangun   # cetak baris tracker (markdown) ke stdout

Sumber temuan:
  keuangan    docs/finance/AUDIT_KEUANGAN_2026-11-13.md                  GL SL IC IV UX DB FY FX RP RC IA
  tambahan    docs/finance/rencana-2026-11-13/11_TEMUAN_TAMBAHAN.md      KM CR PM TX AG PY
  konfigurasi docs/audit/konfigurasi-peran-2026-11-13/ (semua .md)      KF PR KP MB (+ KF-UX, PR-UX satu baris)

Yang dicetak: jumlah per awalan, ID kembar di tracker, ID sumber yang belum ada di tracker, ID tracker (bagian paket ini)
yang tidak ada di sumber, dan baris yang kolom Fase-nya berbeda dari docs/blueprint/INDEKS_UNIT.md.
"""
import collections
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TRACKER = ROOT / "docs/reviews/TRACKER.md"
INDEKS = ROOT / "docs/blueprint/INDEKS_UNIT.md"
SUMBER = {
    "keuangan": ([ROOT / "docs/finance/AUDIT_KEUANGAN_2026-11-13.md"],
                 ["GL", "SL", "IC", "IV", "UX", "DB", "FY", "FX", "RP", "RC", "IA"]),
    "tambahan": ([ROOT / "docs/finance/rencana-2026-11-13/11_TEMUAN_TAMBAHAN.md"],
                 ["KM", "CR", "PM", "TX", "AG", "PY"]),
    "konfigurasi": (sorted((ROOT / "docs/audit/konfigurasi-peran-2026-11-13").rglob("*.md")),
                    ["KF", "PR", "KP", "MB"]),
}
JUDUL_BAGIAN = {
    "keuangan": "Audit keuangan — paket 2026-11-13",
    "tambahan": "Temuan tambahan riset modul — paket 2026-11-13",
    "konfigurasi": "Audit konfigurasi dan peran — paket 2026-11-13",
}
TINGKAT = ("Kritis", "Tinggi", "Sedang", "Rendah", "Keputusan")
# Tingkat bagian §3.x laporan keuangan yang tabelnya tidak punya kolom tingkat.
TINGKAT_BAGIAN = {"3.1": "Kritis", "3.2": "Tinggi", "3.3": "Tinggi", "3.4": "Tinggi", "3.5": "Tinggi",
                  "3.6": "Tinggi", "3.7": "Tinggi", "3.8": "Sedang", "3.9": "Rendah"}


def bersih(t: str) -> str:
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"\*\*|\[[^\]]*\]|✔|\([^)]*dijalankan[^)]*\)", "", t)
    t = re.sub(r"\s+", " ", t).strip(" .;—-")
    if len(t) > 150:
        t = t[:147].rsplit(" ", 1)[0] + "…"
    return t.replace("|", "/")


def ids_dari_sel(sel: str, awalan):
    """'UX-09…17' / 'IA-14, 15' / 'FY-16, 19, 20' / 'GL-01 ✔' → daftar ID."""
    sel = re.sub(r"\*\*|✔|\([^)]*\)|\[[^\]]*\]", " ", sel)
    m = re.match(r"\s*(" + "|".join(awalan) + r")-(\d+)((?:\s*(?:…|\.\.|,)\s*\d+)*)\s*$", sel)
    if not m:
        return []
    p, a, ekor = m.group(1), int(m.group(2)), m.group(3)
    hasil = [a]
    r = re.match(r"\s*(?:…|\.\.)\s*(\d+)", ekor)
    if r:
        hasil = list(range(a, int(r.group(1)) + 1))
    else:
        hasil += [int(x) for x in re.findall(r"\d+", ekor)]
    return [f"{p}-{n:02d}" for n in hasil]


def temuan_sumber(nama):
    berkas, awalan = SUMBER[nama]
    hasil = collections.OrderedDict()
    for f in berkas:
        teks = f.read_text(encoding="utf-8")
        bagian = ""
        kepala = []
        rendah = []
        for baris in teks.splitlines():
            m = re.match(r"^###\s+(\d+\.\d+)", baris)
            if m:
                bagian = m.group(1)
            if baris.startswith("| ID ") or baris.startswith("| # "):
                kepala = [c.strip().lower() for c in baris.strip("|").split("|")]
                continue
            if not baris.startswith("| "):
                # §3.9 laporan keuangan: "GL-11 teks · GL-12 teks"
                if nama == "keuangan" and bagian == "3.9":
                    rendah.append(baris)
                continue
            sel = [c.strip() for c in baris.strip().strip("|").split("|")]
            ids = ids_dari_sel(sel[0], awalan)
            if not ids:
                continue
            tingkat = next((c for c in sel[1:3] if c in TINGKAT), "") or TINGKAT_BAGIAN.get(bagian, "")
            kol = 1
            if "temuan" in kepala:
                kol = kepala.index("temuan")
            elif "ringkas" in kepala:
                kol = kepala.index("ringkas")
            elif sel[1:2] and sel[1] in TINGKAT:
                kol = 2
            judul = bersih(sel[kol]) if kol < len(sel) else ""
            for i in ids:
                # Baris pertama yang punya judul berisi kalimat menang; daftar singkat (mis. tabel peta) tidak.
                lama = hasil.get(i)
                if lama is None or (not lama["tingkat"] and tingkat) or (len(lama["judul"]) < 25 <= len(judul)):
                    hasil[i] = {"judul": judul or (lama or {}).get("judul", ""),
                                "tingkat": tingkat or (lama or {}).get("tingkat", "")}
        for m in re.finditer(r"\b((?:" + "|".join(awalan) + r")-\d+)\s+([^·]+)", " ".join(rendah)):
            hasil.setdefault(m.group(1), {"judul": bersih(m.group(2)), "tingkat": "Rendah"})
    if nama == "konfigurasi":
        hasil["KF-UX"] = {"judul": "28 temuan bahasa dan susunan layar Pusat Pengaturan (lampiran A)", "tingkat": "Sedang"}
        hasil["PR-UX"] = {"judul": "44 temuan layar peran dan izin (lampiran B)", "tingkat": "Sedang"}
    return hasil


def baca_indeks():
    fase = {}
    rx = r"(?:PK-\d+|(?:PR|KF|KP|MN|KM|CR|PM|TX|PY|AG)-T\d+)"
    for baris in INDEKS.read_text(encoding="utf-8").splitlines():
        c = [x.strip() for x in baris.split("|")]
        if len(c) >= 10 and re.fullmatch(rx, c[2] or ""):
            for t in re.findall(r"\b[A-Z]{2}(?:-UX)?-\d+\b|\b(?:KF|PR)-UX\b", c[6]):
                fase.setdefault(t, c[2])
    return fase


def baca_tracker():
    rows = []
    bagian = ""
    for baris in TRACKER.read_text(encoding="utf-8").splitlines():
        if baris.startswith("## "):
            bagian = baris[3:].strip()
        m = re.match(r"^\| ([A-Z]{2}-(?:UX|\d+)) \|", baris)
        if m:
            sel = [c.strip() for c in baris.strip().strip("|").split("|")]
            rows.append({"id": m.group(1), "bagian": bagian, "sel": sel})
    return rows


def main() -> int:
    fase = baca_indeks()
    sumber = {n: temuan_sumber(n) for n in SUMBER}
    if "--bangun" in sys.argv:
        for n, isi in sumber.items():
            print(f"\n## {JUDUL_BAGIAN[n]}\n")
            print("| ID | Judul | Prio | Fase | Status | Berlaku di HEAD | Commit perbaikan | Laporan |")
            print("|---|---|---|---|---|---|---|---|")
            for i, v in isi.items():
                print(f"| {i} | {v['judul']} | {v['tingkat'] or '—'} | {fase.get(i, '—')} | open | "
                      f"belum dicek — diisi unit pemegang | — | — |")
        return 0

    tracker = baca_tracker()
    paket = [r for r in tracker if r["bagian"] in JUDUL_BAGIAN.values()]
    di_tracker = collections.Counter(r["id"] for r in paket)
    masalah = 0
    for n, isi in sumber.items():
        per = collections.Counter(i.split("-")[0] for i in isi)
        print(f"{n:12} {len(isi):4} ID  " + " ".join(f"{k} {v}" for k, v in per.items()))
    semua = {i for isi in sumber.values() for i in isi}
    kembar = sorted(k for k, v in di_tracker.items() if v > 1)
    belum = sorted(semua - set(di_tracker))
    asing = sorted(set(di_tracker) - semua)
    beda = sorted(f"{r['id']}: tracker {r['sel'][3]} ≠ indeks {fase.get(r['id'], '—')}" for r in paket
                  if r["sel"][3] != fase.get(r["id"], "—"))
    tanpa = sorted(i for i in semua if i not in fase)
    for judul, daftar in (("ID kembar di tracker", kembar), ("ID sumber belum di tracker", belum),
                          ("ID tracker tidak ada di sumber", asing), ("Fase berbeda dari indeks", beda)):
        print(f"{judul}: {len(daftar)}" + (f" — {', '.join(daftar[:40])}" if daftar else ""))
        masalah += len(daftar)
    print(f"Tidak dipegang unit mana pun di indeks (Fase —): {len(tanpa)}" + (f" — {', '.join(tanpa)}" if tanpa else ""))
    print(f"Baris paket di tracker: {len(paket)} · status open: {sum(1 for r in paket if r['sel'][4] == 'open')}")
    return 1 if masalah else 0


if __name__ == "__main__":
    sys.exit(main())
