#!/usr/bin/env python3
"""INV-ROLE-02 — TOMBOL & PANGGILAN DATA DI LAYAR MENGIKUTI IZIN, BUKAN NAMA PERAN (ratchet, unit PR-T7).

MASALAH YANG DICEGAH (audit konfigurasi & peran 13 Nov 2026, PR-11 / PR-UX-08)
================================================================================
Server memutuskan boleh/tidak dari IZIN (`require_permission`), tetapi layar masih menyalakan tombol dari NAMA PERAN:
`roleIs(role, ["admin", "manager"])`, `["admin", "md"].includes(user.role)`, `user.role === "sales"`. Akibatnya dua arah:
  · peran kustom TANPA peran dasar yang diberi izin tidak melihat tombol kerjanya (daftar nama tidak pernah cocok);
  · peran berdasar Manajer yang izinnya dicabut tetap melihat tombol yang lalu ditolak 403 (`roleIs` ikut peran dasar).
Penjaga lama (`verify_role_label.py` CHECK 4) hanya memeriksa layar uang/pajak/alur pesanan.

YANG DIHITUNG per berkas di `frontend/src` (tanpa `__tests__`, tanpa komentar)
  · `roleIs(`, `roleSatisfies(`, `roleRank(`;
  · `.includes(<x>)` yang argumennya berakhiran `role` (`.includes(role)`, `.includes(user?.role)`, `.includes(userRole)`);
  · `<x>role ===|!==|==|!= "<id peran>"` (dan kebalikannya) — 13 id peran bawaan dibaca dari `backend/role_registry.py`.
DIKECUALIKAN: registry & rancangan menu (`config/roles.js`, `navMeta.js`, `navStructure.js`, `hubTabs.js`,
`navigationConfig.js`), tombol masuk cepat (`components/LoginScreen.jsx`), tur panduan (`data/tourDefinitions.js`), dan
BARIS berpenanda `// tata-letak: <alasan>` (atau `/* tata-letak: <alasan> */`) — memilih tata letak/label, bukan wewenang.

RATCHET: garis dasar `scripts/guardrails/baselines/role_gate_ui.json` — jumlah per berkas hanya boleh turun; berkas
baru dengan jumlah > 0 = MERAH. Tiap berkas di garis dasar boleh membawa catatan unit pemegangnya (`pemegang`).

Pakai:
    python scripts/guardrails/verify_role_gate_ui.py
    python scripts/guardrails/verify_role_gate_ui.py --self-test
    python scripts/guardrails/verify_role_gate_ui.py --update     # kencangkan garis dasar (hanya turun)
    python scripts/guardrails/verify_role_gate_ui.py --init       # tulis garis dasar (HANYA saat penjaga dibuat)
    python scripts/guardrails/verify_role_gate_ui.py --list       # cetak tiap baris yang terhitung
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import ROOT, Guard, G, R, X  # noqa: E402
from _ratchet import BASE_DIR, SRC, compare, iter_sources, load_baseline, strip_comments, tightened  # noqa: E402

NAME = "role_gate_ui"
BE_REGISTRY = ROOT / "backend" / "role_registry.py"
EXEMPT = {
    "config/roles.js", "config/navMeta.js", "config/navStructure.js", "config/hubTabs.js",
    "config/navigationConfig.js", "components/LoginScreen.jsx", "data/tourDefinitions.js",
}
MARKER = re.compile(r"(?://|/\*)\s*tata-letak:\s*\S")
NOTE = ("Garis dasar ratchet INV-ROLE-02 (gerbang nama peran di layar: roleIs/roleSatisfies/roleRank, "
        ".includes(…role), role === \"<id>\"), dibuat unit PR-T7. Hanya boleh TURUN; kencangkan dengan --update. "
        "`pemegang` = unit yang akan menghapus sisa baris berkas itu.")


def role_ids() -> tuple:
    """13 id peran bawaan dari `backend/role_registry.py` (dibaca tanpa mengimpor FastAPI)."""
    txt = BE_REGISTRY.read_text(encoding="utf-8")
    blok = re.search(r"ROLES:\s*Dict\[str, Dict\[str, Any\]\]\s*=\s*\{(.*?)\n\}\n", txt, re.S)
    return tuple(re.findall(r'^    "(\w+)":\s*\{', blok.group(1) if blok else "", re.M))


def _patterns(ids: tuple):
    alt = "|".join(sorted(ids, key=len, reverse=True))
    op = r"\s*(?:===|!==|==|!=)\s*"
    return [
        ("roleIs", re.compile(r"(?<![\w$.])roleIs\s*\(")),
        ("roleSatisfies", re.compile(r"(?<![\w$.])roleSatisfies\s*\(")),
        ("roleRank", re.compile(r"(?<![\w$.])roleRank\s*\(")),
        # `<x>role === "<id>"` — `<x>role` = pengenal berakhiran role (`role`, `user?.role`, `userRole`, `approver_role`,
        # `JSON.parse(…)?.role`); `roleName === …` tidak.
        ("role === id", re.compile(r"(?<![\w$])[\w$]*[Rr]ole" + op + r"([\"'])(?:" + alt + r")\1")),
        ("id === role", re.compile(r"([\"'])(?:" + alt + r")\1" + op + r"[\w$.?()\[\]\"' ]*?[Rr]ole(?![\w$])")),
    ]


INCLUDES = re.compile(r"\.includes\(")


def _includes_role(line: str) -> list:
    """`.includes(<argumen>)` yang argumennya (sampai kurung penutup pasangannya) berakhiran `role`/`Role`."""
    out = []
    for m in INCLUDES.finditer(line):
        depth, i, quote = 1, m.end(), ""
        while i < len(line) and depth:
            ch = line[i]
            if quote:
                if ch == "\\":
                    i += 1
                elif ch == quote:
                    quote = ""
            elif ch in "\"'`":
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        arg = line[m.end():i - 1] if depth == 0 else ""
        if re.search(r"(?<![\w$])[\w$]*[Rr]ole\s*$", arg) and "," not in arg.split("(")[0]:
            out.append(line[m.start():i][:60])
    return out


PATTERNS = _patterns(role_ids())


def hits(text: str, patterns=None) -> list:
    """→ [(baris, jenis, potongan)] — komentar dibuang; baris ber-`tata-letak:` tidak dihitung."""
    patterns = patterns or PATTERNS
    raw = text.splitlines()
    code = strip_comments(text).splitlines()
    out = []
    for i, line in enumerate(code):
        if i < len(raw) and MARKER.search(raw[i]):
            continue
        for frag in _includes_role(line):
            out.append((i + 1, "includes(role)", frag))
        for kind, pat in patterns:
            for m in pat.finditer(line):
                out.append((i + 1, kind, m.group(0)[:60]))
    return out


def count(text: str, patterns=None) -> int:
    return len(hits(text, patterns))


def current_counts() -> dict:
    out = {}
    for rel, text in iter_sources(lambda r: r in EXEMPT):
        n = count(text)
        if n:
            out[rel] = n
    return out


def load_holders() -> dict:
    p = BASE_DIR / f"{NAME}.json"
    if not p.exists():
        return {}
    return dict(json.loads(p.read_text(encoding="utf-8")).get("pemegang") or {})


def write(files: dict, holders: dict) -> str:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    p = BASE_DIR / f"{NAME}.json"
    keep = {k: files[k] for k in sorted(files) if files[k] > 0}
    data = {"_catatan": NOTE, "total": sum(keep.values()), "files": keep,
            "pemegang": {k: holders[k] for k in sorted(holders) if k in keep}}
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return str(p)


def main() -> int:
    cur = current_counts()
    if "--list" in sys.argv:
        for rel, text in iter_sources(lambda r: r in EXEMPT):
            for ln, kind, frag in hits(text):
                print(f"{rel}:{ln}\t{kind}\t{frag}")
        return 0
    if "--init" in sys.argv:
        p = write(cur, load_holders())
        print(f"garis dasar ditulis: {p} ({len(cur)} berkas, {sum(cur.values())} gerbang nama peran)")
        return 0
    base = load_baseline(NAME)
    holders = load_holders()
    g = Guard("INV-ROLE-02", "tombol & panggilan data di layar mengikuti izin, bukan nama peran")
    if not (BASE_DIR / f"{NAME}.json").exists():
        g.add("garis dasar scripts/guardrails/baselines/role_gate_ui.json tidak ada — jalankan dengan --init SEKALI.")
        return g.finish()
    g.bump(len(cur) + len(base) + 1)
    if len(role_ids()) < 13:
        g.add(f"registry peran backend/role_registry.py terbaca {len(role_ids())} peran (< 13) — pembaca rusak?")
    naik, baru, turun = compare(cur, base)
    for rel, n, b in naik:
        g.add(f"{rel} — gerbang nama peran NAIK {b} → {n}. Pakai can(perms, sumber_daya, aksi) yang sama dengan "
              "require_permission endpoint-nya (02_STANDAR §3.1 Z2); tata letak murni: tandai `// tata-letak: <alasan>`.")
    for rel, n, _ in baru:
        g.add(f"{rel} — berkas BARU memutuskan dari nama peran ({n}×). Pakai can(perms, sumber_daya, aksi) "
              "atau bendera boolean dari server; tata letak murni: `// tata-letak: <alasan>`.")
    print(f"  berkas bergerbang nama peran: {len(cur)} (garis dasar {len(base)}) · "
          f"gerbang: {sum(cur.values())} (garis dasar {sum(base.values())})")
    for rel in sorted(base):
        if rel in cur and rel in holders:
            print(f"    · {rel}: {cur[rel]} — {holders[rel]}")
        elif rel in cur:
            print(f"    · {rel}: {cur[rel]} — (tanpa catatan pemegang)")
    if turun:
        print(f"  turun di {len(turun)} berkas (garis dasar bisa dikencangkan dengan --update):")
        for rel, n, b in turun[:20]:
            print(f"    ↓ {rel}: {b} → {n}")
    if "--update" in sys.argv and not naik and not baru:
        p = write(tightened(cur, base), holders)
        print(f"  garis dasar dikencangkan: {p}")
    return g.finish()


def self_test() -> int:
    gagal = 0

    def cek(nama, ok, rinci=""):
        nonlocal gagal
        print(f"  {'✓' if ok else '✗'} {nama}" + (f"  · {rinci}" if rinci else ""))
        gagal += 0 if ok else 1

    ids = role_ids()
    cek("13 id peran terbaca dari backend/role_registry.py", len(ids) == 13, " ".join(ids))
    # Salinan berkas nyata yang bersih (tanpa gerbang nama peran) → disisipi dua pelanggaran + satu baris tata letak.
    asal = None
    for rel, text in iter_sources(lambda r: r in EXEMPT):
        if rel.endswith(".jsx") and count(text) == 0 and len(text) > 400:
            asal = (rel, text)
            break
    cek("ada berkas bersih untuk disalin", asal is not None)
    if asal is None:
        return 1
    rel, text = asal
    sisip_1 = '\nconst bolehA = roleIs(role, ["manager"]);\n'
    sisip_2 = '\nconst bolehB = ["admin"].includes(user.role);\n'
    tata = '\nconst appHp = roleIs(user.role, ["driver"]);   // tata-letak: aplikasi HP pengemudi (bukan wewenang)\n'
    probe = SRC / "features" / "__poc_role_gate_probe.jsx"
    try:
        probe.write_text(text + sisip_1 + sisip_2 + tata, encoding="utf-8")
        cur = current_counts()
        n = cur.get("features/__poc_role_gate_probe.jsx", 0)
        cek("2 sisipan tertangkap (roleIs + [..].includes(user.role))", n == 2, f"{n} terhitung di salinan {rel}")
        naik, baru, _ = compare(cur, load_baseline(NAME))
        cek("salinan bersisipan MEMERAH sebagai berkas baru", any(r == "features/__poc_role_gate_probe.jsx" for r, _, _ in baru))
        cek("1 baris `// tata-letak:` lolos", count(tata) == 0 and count(tata.replace("// tata-letak:", "//")) == 1)
        cek("penanda tanpa alasan tidak diakui", count('roleIs(r, ["md"]); // tata-letak:\n') == 1)
    finally:
        probe.unlink(missing_ok=True)
    cek("komentar tidak dihitung", count('// dulu: roleIs(role, ["admin"])\n/* ["admin"].includes(role) */\n') == 0)
    cek("role === \"admin\" terhitung", count('const a = currentUser?.role === "admin";') == 1)
    cek("\"sales\" !== user.role terhitung", count('if ("sales" !== user.role) x();') == 1)
    cek("perbandingan peran DOKUMEN berakhiran role terhitung", count('const ok = row.required_role === "manager";') == 1)
    cek("id bukan peran tidak dihitung", count('const a = user.role === "direksi"; const b = tab === "admin";') == 0)
    cek("can(...) tidak dihitung", count('const a = can(perms, "rnd", "assess");') == 0)
    cek("X_ROLES.includes(userRole) terhitung", count("const a = BILL_APPROVERS.includes(userRole);") == 1)
    cek("[..].includes(JSON.parse(…)?.role) terhitung",
        count('return AI_ROLES.includes(JSON.parse(localStorage.getItem("kn_user") || "null")?.role);') == 1)
    cek("JSON.parse(…)?.role === \"admin\" terhitung", count('const a = JSON.parse(x || "null")?.role === "admin";') == 1)
    cek("roles.includes(x) bukan peran tidak dihitung", count("const a = list.includes(roleName); const b = x.roles.includes(r);") == 0)
    naik, baru, turun = compare({"a.jsx": 3, "b.jsx": 1, "c.jsx": 1}, {"a.jsx": 2, "c.jsx": 2})
    cek("naik terdeteksi", naik == [("a.jsx", 3, 2)])
    cek("berkas baru terdeteksi", baru == [("b.jsx", 1, 0)])
    cek("turun = hijau + dicatat", turun == [("c.jsx", 1, 2)])
    cek("--update hanya menurunkan", tightened({"a.jsx": 5, "c.jsx": 1}, {"a.jsx": 2, "c.jsx": 2, "d.jsx": 1}) == {"a.jsx": 2, "c.jsx": 1})
    print(f"{G if not gagal else R}  SELF-TEST {'HIJAU' if not gagal else 'MERAH'} ({gagal} gagal){X}")
    return gagal


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(1 if self_test() else 0)
    raise SystemExit(main())
