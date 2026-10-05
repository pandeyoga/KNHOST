"""Tanya KN F2.4 — pemeriksa angka: setiap angka di jawaban harus ada di hasil tool giliran itu."""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

# KN-E39 — tanda minus ikut dibaca; tahun hanya dilewati bila konteksnya tanggal; toleransi = pembulatan tampilan.
_NUM = re.compile(r"(?<![\w/.])([-\u2212])?(Rp\s?)?(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?\s?((?-i:M)|miliar|jt|juta|rb|ribu|%)?(?![\w/])", re.I)
_SCALE = {"m": 1e9, "miliar": 1e9, "jt": 1e6, "juta": 1e6, "rb": 1e3, "ribu": 1e3}
_MONTHS = r"\b(jan|feb|mar|apr|mei|jun|jul|agu|agt|sep|okt|nov|des)[a-z]*"
_SKIP_CTX = re.compile(
    rf"(\d{{1,2}}\s{_MONTHS}(\s20\d{{2}})?)|({_MONTHS}\s20\d{{2}})|((tahun|thn|th\.?|kuartal|q[1-4])\s20\d{{2}})"
    rf"|(\d{{1,2}}\s?[\u2013-]\s?\d{{1,2}}\s{_MONTHS})"
    r"|(\d{1,2}[/-]\d{1,2}[/-]20\d{2})|(20\d{2}-\d{2}(-\d{2})?)|(\d+\s(teratas|terbawah|besar))"
    r"|(\d+\s(hari|minggu|bulan|tahun)\s(terakhir|ke\sdepan|lalu|sebelumnya|mendatang))"
    r"|(\b([01]?\d|2[0-3]):[0-5]\d\b)|(\b([01]?\d|2[0-3])\.[0-5]\d\s?(WIB|WITA|WIT)\b)"
    r"|(\b20\d{2}\b(?!\s?(m|meter|yd|yard|kg|roll|pcs|rb|ribu|jt|juta|%|,\d)))", re.I)


def extract_numbers(text: str) -> List[Dict[str, Any]]:
    out = []
    masked = _SKIP_CTX.sub(lambda m: " " * len(m.group(0)), text or "")
    for m in _NUM.finditer(masked):
        neg, rp = bool(m.group(1)), m.group(2)
        whole, frac, suf = m.group(3).replace(".", ""), m.group(4), (m.group(5) or "").lower()
        val = float(whole + ("." + frac if frac else ""))
        scale = _SCALE.get(suf, 1.0)
        val *= scale
        if val < 10 and suf != "%" and not rp:
            continue
        decimals = len(frac) if frac else 0
        out.append({"text": m.group(0).strip(), "value": -val if neg else val, "signed": neg, "pct": suf == "%",
                    "scaled": suf in _SCALE, "decimals": decimals, "tol": 0.5 * 10 ** (-decimals) * scale})
    return out


def _walk(obj: Any) -> Iterable[float]:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        yield float(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _walk_labels(obj: Any) -> Iterable[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_labels(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_labels(v)


_KN_BLOCK = re.compile(r"```kn-[\w-]+.*?```", re.S)


def _digits(s: str) -> List[float]:
    return [float(x) for x in re.findall(r"\d+", s or "")]


def verify(text: str, results: List[Dict[str, Any]], question: str = "") -> Dict[str, Any]:
    data = [{k: r.get(k) for k in ("rows", "totals", "compare", "sections", "candidates", "document")} for r in results]
    pool = [v for d in data for v in _walk(d)]
    # Angka di label/judul/argumen hasil (umur "b1_30", "PO-00011", "> 60 hari"), jumlah baris ("12 PO"),
    # dan angka yang diulang dari pertanyaan ("10 pelanggan") bukan angka karangan.
    meta = [{k: r.get(k) for k in ("title", "columns", "args")} for r in results]
    pool += [v for d in data + meta for lbl in _walk_labels(d) for v in _digits(lbl)]
    pool += [v for m in meta for v in _walk(m.get("args"))]
    pool += [float(len(r.get("rows") or [])) for r in results] + _digits(question)
    pool += [n["value"] for r in results for n in extract_numbers(str(r.get("definition") or ""))]
    unmatched = []
    nums = extract_numbers(_KN_BLOCK.sub(" ", text or ""))   # blok kn-* = rujukan tabel/saran lanjutan, bukan klaim
    for n in nums:
        tol = n["tol"] + abs(n["value"]) * 1e-6
        if n["signed"]:
            hit = any(abs(v - n["value"]) <= tol for v in pool)
        else:   # tanpa tanda: "turun 5.000" boleh mencocokkan delta -5000
            hit = any(abs(abs(v) - n["value"]) <= tol for v in pool)
        if not hit:
            unmatched.append(n["text"])
    return {"checked": len(nums), "unmatched": unmatched, "ok": not unmatched}
