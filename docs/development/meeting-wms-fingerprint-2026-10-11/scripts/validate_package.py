from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
d = json.loads((ROOT / "BACKLOG.json").read_text(encoding="utf-8"))
errors, warnings = [], []
reqs = {r["id"]: r for r in d["requirements"]}
phases = {p["id"]: p for p in d["phases"]}
decs = {x["id"]: x for x in d["decisions"]}
tests = {t["id"]: t for t in d["acceptance"]}
if len(reqs) != len(d["requirements"]) or set(reqs) != {f"IMP-{n:02d}" for n in range(1,36)}:
    errors.append("Requirement IDs must be unique IMP-01..35")
if len(phases) != len(d["phases"]) or set(phases) != {f"P{n:02d}" for n in range(11)}:
    errors.append("Phase IDs must be unique P00..P10")
if len(decs) != len(d["decisions"]) or set(decs) != {f"DEC-{n:02d}" for n in range(1,17)}:
    errors.append("Decision IDs must be unique DEC-01..16")
if len(tests) != len(d["acceptance"]) or set(tests) != {f"ACC-{n:02d}" for n in range(67)}:
    errors.append("Acceptance IDs must be unique ACC-00..66")
statuses = {"not_started", "in_progress", "waiting_decision", "waiting_hardware", "implemented_pending_validation", "validated", "reopened"}
for r in d["requirements"]:
    if r["primary_phase"] not in phases or r["status"] not in statuses:
        errors.append(f"Invalid phase/status: {r['id']}")
    if any(t not in tests for t in r["acceptance_ids"]) or not r["acceptance_ids"]:
        errors.append(f"Missing/invalid acceptance: {r['id']}")
    if any(x not in decs for x in r["decision_ids"]):
        errors.append(f"Invalid decision: {r['id']}")
    if r["status"] == "validated":
        if not r.get("verified_commit") or not r.get("evidence"):
            errors.append(f"Validated without commit/evidence: {r['id']}")
        unresolved = [x for x in r["decision_ids"] if decs[x]["status"] not in {"confirmed", "not_applicable"}]
        if unresolved:
            warnings.append(f"Review unresolved business decisions for validated {r['id']}: {unresolved}")
visiting, visited = set(), set()
def visit(pid):
    if pid in visiting:
        errors.append(f"Dependency cycle at {pid}"); return
    if pid in visited: return
    visiting.add(pid)
    for dep in phases[pid]["dependencies"]:
        if dep not in phases: errors.append(f"Unknown dependency {pid}->{dep}")
        else: visit(dep)
    visiting.remove(pid); visited.add(pid)
for p in d["phases"]:
    visit(p["id"])
    if p["status"] not in statuses: errors.append(f"Invalid phase status {p['id']}")
    if any(x not in reqs for x in p["requirements"]):
        errors.append(f"Unknown owned requirement {p['id']}")
    else:
        expected = {r["id"] for r in d["requirements"] if r["primary_phase"] == p["id"]}
        if set(p["requirements"]) != expected:
            errors.append(f"Owned requirement list differs from primary_phase {p['id']}")
    if p["status"] == "validated":
        if not p.get("verified_commit") or not p.get("evidence"):
            errors.append(f"Validated phase without commit/evidence {p['id']}")
        if any(reqs[x]["status"] != "validated" for x in p["requirements"] if x in reqs):
            errors.append(f"Phase validated with unfinished requirements {p['id']}")
        if p["id"] == "P10" and any(r["status"] != "validated" for r in d["requirements"]):
            errors.append("P10 validated while some of 35 requirements remain unfinished")
for x in d["decisions"]:
    if x["status"] not in {"open", "proposed", "confirmed", "not_applicable"}: errors.append(f"Invalid decision status {x['id']}")
    if x["status"] == "confirmed" and not x.get("confirmation_ref"): errors.append(f"No confirmation source {x['id']}")
    if x["status"] == "not_applicable" and not x.get("reason"): errors.append(f"No reason {x['id']}")
for t in d["acceptance"]:
    if t["status"] not in {"not_run", "pass", "fail", "waiting_decision", "waiting_hardware"}: errors.append(f"Invalid test status {t['id']}")
    if t["status"] == "pass" and (not t.get("verified_commit") or not t.get("evidence")):
        errors.append(f"Pass without commit/evidence {t['id']}")
for file in ROOT.rglob("*.md"):
    for target in re.findall(r"\]\(([^)]+)\)", file.read_text(encoding="utf-8")):
        if target.startswith(("http:", "https:", "#", "mailto:")): continue
        path = target.split("#",1)[0]
        if path and not (file.parent / path).exists(): errors.append(f"Broken local link {file.relative_to(ROOT)}: {target}")
print(json.dumps({"requirements":len(reqs), "phases":len(phases), "decisions":len(decs), "acceptance":len(tests), "errors":errors, "warnings":warnings}, ensure_ascii=False, indent=2))
raise SystemExit(1 if errors else 0)
