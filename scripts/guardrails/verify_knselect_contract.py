"""FE-02 (review 2026-10-20) — `KNSelect` hanya menerima `onValueChange`.

`onChange` pada `<KNSelect>` dibuang diam-diam: pilihan tampak bisa dibuka tetapi nilai form tidak
pernah berubah (9 lokasi Interco). Guardrail ini gagal bila ada `<KNSelect ... onChange=...>` tanpa
`onValueChange`.

Usage: python scripts/guardrails/verify_knselect_contract.py
Exit 1 bila ada temuan (dicetak file:baris).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "frontend" / "src"
TAG = re.compile(r"<KNSelect\b(.*?)/?>", re.S)


def scan() -> list:
    hits = []
    for path in sorted(SRC.rglob("*.jsx")) + sorted(SRC.rglob("*.js")):
        if "node_modules" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in TAG.finditer(text):
            props = m.group(1)
            if re.search(r"\bonChange\s*=", props) and not re.search(r"\bonValueChange\s*=", props):
                line = text.count("\n", 0, m.start()) + 1
                hits.append(f"{path.relative_to(ROOT).as_posix()}:{line}")
    return hits


def main() -> int:
    hits = scan()
    for h in hits:
        print(f"KNSelect onChange (pakai onValueChange): {h}")
    print(f"verify_knselect_contract: {len(hits)} temuan")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
