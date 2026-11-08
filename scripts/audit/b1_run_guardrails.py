#!/usr/bin/env python3
"""Audit B1 — jalankan guardrail UI secara READ-ONLY dan catat hasilnya.

TIDAK PERNAH memberi `--update`/`--init`/`--write`/`--fix`/`--rebase`/`--self-test` (self-test
`verify_role_label` menulis berkas probe ke `frontend/src`). Tiap skrip dijalankan tanpa argumen
(kecuali `audit_i18n_id.py --strict`, yang read-only). Sebelum & sesudah, `git status --porcelain`
dibandingkan; bila ada berkas berubah, daftar itu dicetak supaya bisa dikembalikan.

Usage:  PYTHONUTF8=1 python scripts/audit/b1_run_guardrails.py [--out DIR]
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAMES = ["custom_modals", "detail_modal", "error_notice", "knselect_contract", "list_export", "modal_dismiss",
         "page_tabs", "picker_portal", "qty_dual", "uom_vocab", "role_label", "entity_label", "view_aliases",
         "blocking_dialogs", "escape_layers", "desk_targets", "home_kpi", "access_catalog_nav", "to_list_bound",
         "numeric_bounds"]


def porcelain():
    r = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True, text=True)
    return set(r.stdout.splitlines())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.environ.get("B1_OUT", ""))
    ap.add_argument("--root", default="", help="akar salinan repo lain (mis. snapshot main di scratchpad)")
    ap.add_argument("--only", default="", help="daftar nama dipisah koma (default: semua)")
    a = ap.parse_args()
    out = Path(a.out) if a.out else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    root = Path(a.root).resolve() if a.root else ROOT
    names = [n for n in NAMES if not a.only or n in a.only.split(",")]
    env = dict(os.environ, PYTHONUTF8="1", NO_COLOR="1")
    before = porcelain()
    results = []
    jobs = [(n, [sys.executable, str(root / "scripts" / "guardrails" / f"verify_{n}.py")]) for n in names]
    if not a.only or "i18n" in a.only:
        jobs.append(("audit_i18n_id --strict", [sys.executable, str(root / "scripts" / "audit_i18n_id.py"), "--strict"]))
    for name, cmd in jobs:
        t0 = time.time()
        try:
            r = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, env=env, timeout=600,
                               encoding="utf-8", errors="replace")
            code, text = r.returncode, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            code, text = "timeout", ""
        dt = round(time.time() - t0, 1)
        tail = [ln for ln in text.splitlines() if ln.strip()][-6:]
        results.append({"name": name, "exit": code, "secs": dt, "tail": tail})
        if out:
            (out / f"{name.split()[0]}.txt").write_text(text, encoding="utf-8")
        print(f"{name:28} exit={code} ({dt}s) :: {' | '.join(tail[-2:])[:220]}")
    after = porcelain()
    changed = sorted(after - before)
    print("BERKAS BERUBAH SELAMA GUARDRAIL:", changed or "tidak ada")
    if out:
        (out / "summary.json").write_text(json.dumps({"results": results, "changed": changed}, ensure_ascii=False,
                                                     indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
