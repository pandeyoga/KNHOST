"""Perbarui status kasus di audit/coverage.json dari berkas spesifikasi JSON.

Usage: python3 audit/tools/set_status.py <spec.json> [--commit=<sha>]
spec: [{"id": "AUTH-01", "status": "tested_pass", "evidence": ["iterations/..."], "notes": "..."}]
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    spec = json.loads(Path(sys.argv[1]).read_text())
    sha = next((a.split("=", 1)[1] for a in sys.argv[2:] if a.startswith("--commit=")), None) or \
        subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    path = ROOT / "coverage.json"
    data = json.loads(path.read_text())
    by_id = {c["id"]: c for c in data["cases"]}
    for s in spec:
        case = by_id[s["id"]]
        case["current_status"] = s["status"]
        case["tested_commit"] = sha
        case["evidence"] = list(dict.fromkeys((s.get("evidence") or []) + (case.get("evidence") or [])))
        case["notes"] = s.get("notes", case.get("notes", ""))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    from collections import Counter
    print(Counter(c["current_status"] for c in data["cases"]))


main()
