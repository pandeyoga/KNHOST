"""Read-only Git comparison and audit addendum; no checkout or database changes."""
from pathlib import Path
import json
import subprocess

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2] / "work" / "KNHOST-reader-integration-2026-10-18"
OLD = "63c38bd11b49ddfb59cbbfdb915c2e11e16d5c9c"
NEW = "8dab383f764df80737bfe02f887422b3fd72aa70"

def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO, encoding="utf-8").strip()

original = json.loads((OUT / "findings.json").read_text(encoding="utf-8"))
findings = []
for old in original["findings"]:
    row = dict(old)
    row["status_on_latest"] = "confirmed_open"
    row["source"] = [dict(ref) for ref in old["source"]]
    for ref in row["source"]:
        if ref["file"] == "frontend/src/features/finance/interco/IntercoView.jsx":
            ref["lines"] = [212, 315]
        ref["old_blob"] = git("rev-parse", f"{OLD}:{ref['file']}")
        ref["latest_blob"] = git("rev-parse", f"{NEW}:{ref['file']}")
        ref["identical_to_prior"] = ref["old_blob"] == ref["latest_blob"]
    findings.append(row)
report = {
    "previous_baseline": OLD,
    "baseline_sha": NEW,
    "review_date": "2026-10-20",
    "method": "git diff/blob identity and rerun of original JSX renderer reading git show at exact latest SHA",
    "app_or_database_modified": False,
    "evidence": "render-results-8dab.json",
    "status_counts": {"confirmed_open": len(findings), "fixed": 0, "not_applicable": 0},
    "findings": findings,
    "context": [
        "Primary frontend files for all seven findings have identical Git blob IDs.",
        "IntercoView changed return-tab placement, but button/preset path remains; latest references are 212 and 315.",
        "permissions_config.py changed return cutloss permissions/comments; Finance payment_variance.decide remains at line377.",
        "role_registry.py changed Admin Sample labels, not role_in behavior.",
        "Frontend roles.js adds canCurrent/canSeeGrade; the affected files do not call these helpers.",
        "AppViewRouter routes consolidated interco returns; original interco-transactions route still opens the affected forms.",
        "Export frontend files are unchanged; this addendum does not re-run backend export jobs.",
        "RFID custom_admin remains an excluded candidate because Admin is not an allowed custom-role template.",
        "No browser or device UAT is claimed by this addendum."
    ]
}
(OUT / "latest-8dab.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"baseline": NEW, "findings": len(findings), "status_counts": report["status_counts"]}, indent=2))
