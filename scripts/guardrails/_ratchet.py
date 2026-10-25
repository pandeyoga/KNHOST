"""scripts/guardrails/_ratchet.py — util bersama guardrail RATCHET (fase 3 · P1).

Ratchet = jumlah pola usang per berkas HANYA BOLEH TURUN. Baseline disimpan di
`scripts/guardrails/baselines/<nama>.json` ({"_catatan": …, "files": {rel: n}}).

Aturan yang sama untuk semua penjaga ratchet:
  · berkas yang jumlahnya NAIK dari baseline           → MERAH;
  · berkas BARU (tidak ada di baseline) dengan jumlah > 0 → MERAH;
  · jumlah TURUN → hijau + catatan (baseline TIDAK wajib disunting oleh paket paralel P2–P7,
    supaya tidak bentrok di berkas yang sama; P8 mengencangkan dengan `--update`).

Opsi baris perintah:
  --update   kencangkan baseline: tiap berkas = min(baseline, sekarang); berkas 0 dibuang. Tidak pernah menaikkan.
  --init     tulis baseline dari kondisi sekarang (HANYA saat penjaga dibuat — P1).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List

from _common import FRONTEND, ROOT

SRC = FRONTEND / "src"
BASE_DIR = ROOT / "scripts" / "guardrails" / "baselines"


def strip_comments(src: str) -> str:
    """Kosongkan komentar JS (`//`, `/* */`); literal string DIPERTAHANKAN (kelas CSS hidup di string)."""
    out: List[str] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            while i < n and src[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if c == "/" and nxt == "*":
            while i < n and not (src[i] == "*" and i + 1 < n and src[i + 1] == "/"):
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            out.append("  ")
            i += 2
            continue
        if c in ("'", '"', "`"):
            quote = c
            out.append(c)
            i += 1
            while i < n:
                out.append(src[i])
                if src[i] == "\\" and i + 1 < n:
                    out.append(src[i + 1])
                    i += 2
                    continue
                if src[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def iter_sources(exclude: Callable[[str], bool]):
    for path in sorted(list(SRC.rglob("*.jsx")) + list(SRC.rglob("*.js"))):
        rel = str(path.relative_to(SRC)).replace("\\", "/")
        if "__tests__/" in rel or rel.startswith("components/ui/") or exclude(rel):
            continue
        try:
            yield rel, path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue


def load_baseline(name: str) -> Dict[str, int]:
    p = BASE_DIR / f"{name}.json"
    if not p.exists():
        return {}
    return {k: int(v) for k, v in (json.loads(p.read_text(encoding="utf-8")).get("files") or {}).items()}


def write_baseline(name: str, files: Dict[str, int], note: str) -> Path:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    p = BASE_DIR / f"{name}.json"
    data = {"_catatan": note, "total": sum(files.values()),
            "files": {k: files[k] for k in sorted(files) if files[k] > 0}}
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return p


def compare(current: Dict[str, int], baseline: Dict[str, int]):
    """→ (naik, baru, turun) — daftar (rel, sekarang, baseline)."""
    naik, baru, turun = [], [], []
    for rel, n in sorted(current.items()):
        if n <= 0:
            continue
        b = baseline.get(rel)
        if b is None:
            baru.append((rel, n, 0))
        elif n > b:
            naik.append((rel, n, b))
    for rel, b in sorted(baseline.items()):
        n = current.get(rel, 0)
        if n < b:
            turun.append((rel, n, b))
    return naik, baru, turun


def tightened(current: Dict[str, int], baseline: Dict[str, int]) -> Dict[str, int]:
    return {rel: min(b, current.get(rel, 0)) for rel, b in baseline.items() if min(b, current.get(rel, 0)) > 0}
