"""GN-14 — secret scanning repo: file token/kunci & pola credential pada file ter-track.

Usage: python scripts/guardrails/verify_no_secrets.py [--all]
Exit 1 bila ada temuan. Nilai yang cocok TIDAK dicetak (hanya file:baris:jenis).
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BANNED_NAMES = re.compile(r"(^|/)(\.tok(_[\w-]+)?|\.token\.txt|[\w.-]+\.pem|[\w.-]+\.key|credentials\.json|\.env(\.[\w-]+)?)$")
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    "aws_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "stripe_live": re.compile(r"sk_live_[0-9a-zA-Z]{20,}"),
    "openai_key": re.compile(r"sk-(proj-)?[A-Za-z0-9_-]{32,}"),
    "google_api": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "emergent_key": re.compile(r"sk-emergent-[0-9a-zA-Z]{10,}"),
    "slack_token": re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    "github_token": re.compile(r"gh[pousr]_[0-9A-Za-z]{30,}"),
    "bearer_literal": re.compile(r"Bearer\s+[A-Za-z0-9_-]{32,}"),
}
SKIP_DIRS = ("node_modules/", "frontend/build/", "audit/archive/", ".git/")
SKIP_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".ico", ".woff", ".woff2", ".ttf", ".zip", ".lock")


def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        files = [f for f in out.splitlines() if f]
    except Exception:  # noqa: BLE001 — tanpa git: pindai pohon kerja
        files = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file()]
    return [f for f in files if not f.startswith(SKIP_DIRS) and (ROOT / f).is_file()]


def main() -> int:
    findings = []
    for f in tracked_files():
        if BANNED_NAMES.search(f) and not f.endswith((".env.example", "README.key")):
            findings.append((f, 0, "file_terlarang"))
            continue
        if f.endswith(SKIP_EXT):
            continue
        try:
            text = (ROOT / f).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for kind, rx in PATTERNS.items():
                if rx.search(line):
                    findings.append((f, i, kind))
    for f, i, kind in findings:
        print(f"SECRET? {f}:{i} [{kind}]")
    print(f"verify_no_secrets: {len(findings)} temuan")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
