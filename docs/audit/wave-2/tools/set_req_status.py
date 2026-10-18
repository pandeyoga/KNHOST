"""Update status W2-REQ pada requirements-tracker.json + history (implementer berhenti di ready_for_validation)."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument("--ids", required=True)
p.add_argument("--status", required=True, choices=["open", "in_progress", "ready_for_validation", "blocked", "deferred"])
p.add_argument("--commit", default="")
p.add_argument("--evidence", action="append", default=[])
p.add_argument("--note", default="")
a = p.parse_args()
path = ROOT / "requirements-tracker.json"
data = json.loads(path.read_text())
ids = set(a.ids.split(","))
for r in data["requirements"]:
    if r["id"] not in ids:
        continue
    r["status"] = a.status
    if a.commit and a.commit not in r["implementation_commits"]:
        r["implementation_commits"].append(a.commit)
    for e in a.evidence:
        if e not in r["implementation_evidence"]:
            r["implementation_evidence"].append(e)
    r.setdefault("history", []).append({"at": datetime.now(timezone.utc).isoformat(), "status": a.status, "note": a.note})
    ids.discard(r["id"])
if ids:
    raise SystemExit(f"ID tidak dikenal: {sorted(ids)}")
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
print("ok")
