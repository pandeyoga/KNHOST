#!/usr/bin/env python3
"""G-UI-03 — KONTRAS WARNA STANDAR UI GUDANG v1 (KERAS): pasangan token & kelas baku WAJIB lolos WCAG 2.2 AA.

MASALAH YANG DICEGAH (audit B4 §2.2, keputusan K-B4-03): tombol utama putih di atas #007AFF = 4,02:1 dan tombol
bahaya di atas #FF3B30 = 3,55:1 (gagal 1.4.3); teks abu #8E8E93/#9A9BA3 = 3,26/2,77:1; batas isian #D6D7DC = 1,44:1
(gagal 1.4.11). Warna itu dipakai ribuan kali — satu token yang tergeser kembali ke nilai lama merusak semua layar.

Cara kerja (MENJALANKAN, bukan mencari pola): nilai token dibaca dari `frontend/src/styles/tokens.css`, aturan kelas
baku dari stylesheet dalam urutan impor `App.css` (aturan terakhir menang, `var()` diselesaikan), latar rgba
dikomposit di atas putih, lalu rasio dihitung dengan rumus WCAG (luminans relatif sRGB; rasio TIDAK dibulatkan).
  · teks ≥ 4,5:1 (1.4.3) · komponen/batas/fokus ≥ 3:1 (1.4.11)
Keluaran: tabel rasio (dipakai juga di laporan & KN_37).

Pakai:  python scripts/guardrails/verify_ui_contrast.py [--table] [--self-test]
"""
from __future__ import annotations

import os
import re
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(__file__))
from _common import FRONTEND, Guard, G, R, X  # noqa: E402

_SRC = __import__("pathlib").Path(os.environ["KN_UI_SRC"]) if os.environ.get("KN_UI_SRC") else FRONTEND / "src"
STYLES = _SRC / "styles"          # KN_UI_SRC = salinan frontend/src lain (bukti "merah sebelum" di laporan FIX-4)
APP_CSS = _SRC / "App.css"
WHITE = (255, 255, 255)

#: (teks/ikon, latar, minimum, keterangan) — nilai `--x` dibaca dari tokens.css.
TOKEN_PAIRS: List[Tuple[str, str, float, str]] = [
    ("--kn-text", "#FFFFFF", 4.5, "teks utama"),
    ("--kn-text-2", "#FFFFFF", 4.5, "teks sekunder (minimum teks)"),
    ("--kn-text-2", "#F4F5F8", 4.5, "teks sekunder di latar halaman"),
    ("--kn-text-2", "--kn-neutral-soft", 4.5, "teks sekunder di latar netral"),
    ("--kn-neutral", "--kn-neutral-soft", 4.5, "lencana netral/draf"),
    ("#FFFFFF", "--kn-action", 4.5, "tombol utama (teks putih)"),
    ("#FFFFFF", "--kn-action-hover", 4.5, "tombol utama saat disorot"),
    ("--kn-action", "#FFFFFF", 4.5, "tautan / teks aksi"),
    ("--kn-action", "--kn-action-soft", 4.5, "lencana info"),
    ("--kn-success-text", "#FFFFFF", 4.5, "teks berhasil"),
    ("--kn-success-text", "--kn-success-soft", 4.5, "lencana berhasil"),
    ("#FFFFFF", "--kn-success-solid", 4.5, "isian hijau (teks putih)"),
    ("--kn-warning-text", "#FFFFFF", 4.5, "teks perhatian"),
    ("--kn-warning-text", "--kn-warning-soft", 4.5, "lencana perhatian / tanda ragu OCR"),
    ("--kn-text", "--kn-warning-kiosk", 4.5, "kuning kios gate (teks gelap)"),
    ("--kn-danger-text", "#FFFFFF", 4.5, "teks bahaya"),
    ("--kn-danger-text", "--kn-danger-soft", 4.5, "lencana bahaya"),
    ("#FFFFFF", "--kn-danger", 4.5, "tombol bahaya (teks putih)"),
    ("#FFFFFF", "--kn-danger-hover", 4.5, "tombol bahaya saat disorot"),
    ("--kn-special-text", "#FFFFFF", 4.5, "teks khusus (lot/sampel)"),
    ("--kn-special-text", "--kn-special-soft", 4.5, "lencana khusus"),
    ("--kn-field-border", "#FFFFFF", 3.0, "batas isian (1.4.11)"),
    ("--kn-focus", "#FFFFFF", 3.0, "cincin fokus (1.4.11)"),
]

#: Kelas baku: (selektor, properti teks, properti latar, minimum). Latar kosong = putih.
CLASS_RULES: List[Tuple[str, str, str, float]] = [
    (".primary-button", "color", "background", 4.5),
    (".primary-button:hover", "", "background", 4.5),
    (".danger-button", "color", "background", 4.5),
    (".danger-button:hover", "", "background", 4.5),
    (".btn-primary", "color", "background", 4.5),
    (".btn-danger", "color", "background", 4.5),
    (".nav-button.active", "color", "background", 4.5),
    (".kn-pager-btn.is-active", "color", "background", 4.5),
    (".field::placeholder", "color", "", 4.5),
    (".text-muted", "color", "", 4.5),
    (".kn-pager-info", "color", "", 4.5),
    (".field", "border", "", 3.0),
    # FIX-8 (tahap 2) — lencana status baku `StatusBadge` (6 nada B4 §3.9) & keadaan daftar `EmptyState`.
    (".kn-badge.tone-neutral", "color", "background", 4.5),
    (".kn-badge.tone-info", "color", "background", 4.5),
    (".kn-badge.tone-success", "color", "background", 4.5),
    (".kn-badge.tone-warning", "color", "background", 4.5),
    (".kn-badge.tone-danger", "color", "background", 4.5),
    (".kn-badge.tone-special", "color", "background", 4.5),
    (".kn-docno-pt", "color", "background", 4.5),
    (".kn-empty-text", "color", "", 4.5),
    (".kn-views-head", "color", "", 4.5),
]


def hex_rgb(h: str) -> Tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def parse_color(v: str, base=WHITE) -> Optional[Tuple[float, float, float]]:
    v = v.strip()
    m = re.search(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", v)
    if m and not v.startswith("rgba"):
        return tuple(float(x) for x in hex_rgb(m.group(0)))
    m = re.search(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)", v)
    if m:
        r, g, b = (float(m.group(i)) for i in (1, 2, 3))
        a = float(m.group(4)) if m.group(4) else 1.0
        return tuple(a * c + (1 - a) * bc for c, bc in zip((r, g, b), base))
    if v in ("#fff", "white"):
        return 255.0, 255.0, 255.0
    return None


def luminance(rgb) -> float:
    def ch(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg, bg) -> float:
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def load_tokens() -> Dict[str, str]:
    txt = re.sub(r"/\*[\s\S]*?\*/", " ", (STYLES / "tokens.css").read_text(encoding="utf-8"))
    return {m.group(1): m.group(2).strip() for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+);", txt)}


def resolve(v: str, tokens: Dict[str, str]) -> str:
    for _ in range(5):
        m = re.search(r"var\((--[\w-]+)(?:\s*,\s*([^)]+))?\)", v)
        if not m:
            break
        v = v[:m.start()] + tokens.get(m.group(1), m.group(2) or "") + v[m.end():]
    return v


def load_rules() -> Dict[str, Dict[str, str]]:
    """selektor → deklarasi, sesuai urutan @import App.css (yang terakhir menang)."""
    order = re.findall(r'@import\s+"\./styles/([\w.-]+\.css)"', APP_CSS.read_text(encoding="utf-8"))
    rules: Dict[str, Dict[str, str]] = {}
    for name in order:
        txt = re.sub(r"/\*[\s\S]*?\*/", " ", (STYLES / name).read_text(encoding="utf-8"))
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", txt):
            decls = {}
            for d in m.group(2).split(";"):
                if ":" in d:
                    k, v = d.split(":", 1)
                    decls[k.strip()] = v.strip()
            for sel in m.group(1).split(","):
                sel = " ".join(sel.split())
                if sel and not sel.startswith("@"):
                    rules.setdefault(sel, {}).update(decls)
    return rules


def rows() -> List[Tuple[str, str, str, float, float, bool]]:
    tokens = load_tokens()
    out = []
    for fg, bg, need, desc in TOKEN_PAIRS:
        fv, bv = resolve(tokens.get(fg, fg) if fg.startswith("--") else fg, tokens), \
            resolve(tokens.get(bg, bg) if bg.startswith("--") else bg, tokens)
        b = parse_color(bv)
        f = parse_color(fv, b or WHITE)
        r = ratio(f, b) if f and b else 0.0
        out.append((desc, f"{fg} {fv}", f"{bg} {bv}", need, r, bool(f and b) and r >= need))
    rules = load_rules()
    for sel, fprop, bprop, need in CLASS_RULES:
        decl = rules.get(sel, {})
        base_decl = rules.get(sel.split(":")[0], {}) if ":" in sel else decl
        bv = resolve(decl.get(bprop) or base_decl.get(bprop) or "#FFFFFF", tokens) if bprop else "#FFFFFF"
        fv = resolve(decl.get(fprop) or base_decl.get(fprop, ""), tokens) if fprop else \
            resolve(base_decl.get("color", "#FFFFFF"), tokens)
        if fprop == "border":
            fv = resolve(decl.get("border", ""), tokens)
        b = parse_color(bv)
        f = parse_color(fv, b or WHITE)
        r = ratio(f, b) if f and b else 0.0
        out.append((f"kelas {sel}", fv[:40], bv[:40], need, r, bool(f and b) and r >= need))
    for sel, decl in sorted(rules.items()):
        if re.fullmatch(r"\.status-[\w-]+", sel) and "color" in decl and "background" in decl:
            bv, fv = resolve(decl["background"], tokens), resolve(decl["color"], tokens)
            b = parse_color(bv)
            f = parse_color(fv, b or WHITE)
            if f and b:
                r = ratio(f, b)
                out.append((f"lencana {sel}", fv, bv, 4.5, r, r >= 4.5))
    return out


def main() -> int:
    g = Guard("G-UI-03", "kontras token & kelas baku Standar UI Gudang v1 (WCAG 2.2 AA)")
    res = rows()
    if "--table" in sys.argv:
        print("| Pasangan | Teks/ikon | Latar | Syarat | Rasio | Hasil |\n|---|---|---|---|---|---|")
        for desc, f, b, need, r, ok in res:
            print(f"| {desc} | `{f}` | `{b}` | {need:g}:1 | {r:.2f}:1 | {'lolos' if ok else '**gagal**'} |")
    for desc, f, b, need, r, ok in res:
        g.bump()
        if not ok:
            g.add(f"{desc}: {f} di {b} = {r:.2f}:1 < {need:g}:1")
    print(f"  {sum(1 for x in res if x[5])}/{len(res)} pasangan lolos")
    return g.finish()


def self_test() -> int:
    gagal = 0

    def cek(nama, ok):
        nonlocal gagal
        print(f"  {'✓' if ok else '✗'} {nama}")
        gagal += 0 if ok else 1

    cek("putih/hitam = 21:1", abs(ratio((255, 255, 255), (0, 0, 0)) - 21) < 0.01)
    cek("#007AFF teks putih = 4,02:1 (angka audit B4)", abs(ratio((255, 255, 255), hex_rgb("#007AFF")) - 4.02) < 0.01)
    cek("#FF3B30 teks putih = 3,55:1", abs(ratio((255, 255, 255), hex_rgb("#FF3B30")) - 3.55) < 0.01)
    cek("#0058CC teks putih = 6,43:1", abs(ratio((255, 255, 255), hex_rgb("#0058CC")) - 6.43) < 0.01)
    cek("rgba dikomposit di atas putih", parse_color("rgba(0, 0, 0, 0.5)") == (127.5, 127.5, 127.5))
    cek("var() diselesaikan dari token", resolve("var(--a)", {"--a": "#123456"}) == "#123456")
    print(f"{G if not gagal else R}  SELF-TEST {'HIJAU' if not gagal else 'MERAH'} ({gagal} gagal){X}")
    return gagal


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(1 if self_test() else 0)
    raise SystemExit(main())
