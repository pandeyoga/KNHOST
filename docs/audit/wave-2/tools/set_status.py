"""Update status satu/lebih ID pada tracker aktif W2 (tracker.json) + history. Implementer berhenti di
ready_for_validation; verified_fixed hanya oleh auditor. Usage:
  python tools/set_status.py --ids W2-001,W2-002 --status ready_for_validation --commit <sha|uncommitted>
         --evidence iterations/x/regression_results.json [--note "..."] [--phase-file]
"""
import argparse
import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {"open", "in_progress", "ready_for_validation", "blocked"}

p = argparse.ArgumentParser()
p.add_argument("--ids", required=True)
p.add_argument("--status", required=True)
p.add_argument("--commit", default="")
p.add_argument("--evidence", action="append", default=[])
p.add_argument("--note", default="")
a = p.parse_args()
if a.status not in ALLOWED:
    p.error(f"status implementer hanya {sorted(ALLOWED)}")
for ev in a.evidence:
    if not (ROOT / ev).exists():
        p.error(f"evidence tidak ada: {ev}")
path = ROOT / "tracker.json"
data = json.loads(path.read_text())
ids = {i.strip() for i in a.ids.split(",") if i.strip()}
today = datetime.date.today().isoformat()
hit = set()
for f in data["findings"]:
    if f["id"] not in ids:
        continue
    hit.add(f["id"])
    f["status"] = a.status
    if a.commit and a.commit not in f["implementation_commits"]:
        f["implementation_commits"].append(a.commit)
    for ev in a.evidence:
        if ev not in f["implementation_evidence"]:
            f["implementation_evidence"].append(ev)
    f["history"].append({"event": a.status, "date": today, **({"note": a.note} if a.note else {})})
missing = ids - hit
if missing:
    p.error(f"ID tidak ditemukan: {sorted(missing)}")
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
print("updated", sorted(hit), "->", a.status)
