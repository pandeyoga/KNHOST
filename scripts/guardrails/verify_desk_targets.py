"""FE-06 (review 2026-10-20) — target lompatan antrean harus menunjuk layar yang DIRENDER.

`ROLE_DESK_TARGET.price_approval` dulu menunjuk `view: "approvals"`, padahal renderer hanya punya
`price-approvals`: tombol "Putuskan" di Meja Saya membuka halaman kosong. Guardrail ini membaca semua
peta target di `features/sales_admin/workDeskApi.js` (meja per peran, baris antrean, antrean Finance,
gudang, alamat dokumen) dan memastikan setiap `view` punya cabang `activeView === "<view>"` di
`AppViewRouter.jsx`.

Usage: python scripts/guardrails/verify_desk_targets.py
Exit 1 bila ada target yang menunjuk layar hantu (dicetak peta.kunci → view).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "frontend" / "src"
DESK = SRC / "features" / "sales_admin" / "workDeskApi.js"
ROUTER = SRC / "AppViewRouter.jsx"
MAP = re.compile(r"(?:export\s+)?const\s+([A-Z_]+_TARGET)\s*=\s*\{(.*?)\n\};", re.S)
ENTRY = re.compile(r"^\s*([a-z_]+)\s*:\s*\{[^}]*?\bview:\s*\"([^\"]+)\"", re.M)


def rendered_views() -> set:
    return set(re.findall(r'activeView === "([^"]+)"', ROUTER.read_text(encoding="utf-8")))


def targets() -> list:
    out = []
    for m in MAP.finditer(DESK.read_text(encoding="utf-8")):
        for key, view in ENTRY.findall(m.group(2)):
            out.append((m.group(1), key, view))
    return out


def scan() -> list:
    views = rendered_views()
    found = targets()
    if not found:
        return ["peta target tidak terbaca — pola workDeskApi.js berubah, perbarui guardrail ini"]
    return [f"{name}.{key} -> view '{view}' tidak ada di AppViewRouter.jsx"
            for name, key, view in found if view not in views]


def main() -> int:
    hits = scan()
    for h in hits:
        print(f"Target antrean ke layar hantu: {h}")
    print(f"verify_desk_targets: {len(targets())} target diperiksa, {len(hits)} temuan")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
