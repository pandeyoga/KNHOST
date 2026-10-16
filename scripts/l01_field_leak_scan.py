"""L01 (LN-012-T02/T05) — pemindai kebocoran field grade/LOT/asal untuk satu akun.

Memanggil SEMUA endpoint GET tanpa path-param dari OpenAPI (plus endpoint detail umum)
lalu melaporkan kunci JSON sensitif yang masih terkirim. Read-only.
Pakai: python scripts/l01_field_leak_scan.py --email sales.kanda@kainnusantara.id --password demo1234
"""
import argparse
import json
import os
import re
import sys

import requests

SENSITIVE = {
    "grade": re.compile(r"^(grade|grades|grade_.*|.*_grade|.*_grades|by_grade|stock_by_grade)$"),
    "lot": re.compile(r"^(lot|lots|lot_.*|.*_lot|.*_lots|batch_lot_rolls|dye_lot|supplier_lot|by_lot)$"),
    "origin": re.compile(r"^(origin|origin_.*|.*_origin|is_import|import_local)$"),
}
SKIP = re.compile(r"(logout|export|download|pdf|print|stream|sse|events|ws|scan|test|debug|health|ocr)", re.I)


def keys_in(obj, found, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            for cat, rx in SENSITIVE.items():
                if rx.match(str(k)):
                    found.setdefault(cat, set()).add(k)
            keys_in(v, found, k)
    elif isinstance(obj, list):
        for v in obj[:50]:
            keys_in(v, found, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--base", default=os.environ.get("KN_BASE", "http://localhost:8001"))
    ap.add_argument("--entity", default="")
    a = ap.parse_args()
    s = requests.Session()
    r = s.post(f"{a.base}/api/auth/login", json={"email": a.email, "password": a.password}, timeout=30)
    r.raise_for_status()
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    if a.entity:
        s.headers["X-Entity-Id"] = a.entity
    spec = requests.get(f"{a.base}/openapi.json", timeout=60).json()
    paths = [p for p, ops in spec["paths"].items() if "get" in ops and "{" not in p and not SKIP.search(p)]
    leaks, ok, denied = {}, 0, 0
    for p in sorted(paths):
        try:
            resp = s.get(f"{a.base}{p}", timeout=20)
        except Exception:
            continue
        if resp.status_code != 200 or "json" not in resp.headers.get("content-type", ""):
            denied += resp.status_code in (401, 403)
            continue
        ok += 1
        found = {}
        keys_in(resp.json(), found)
        if found:
            leaks[p] = {k: sorted(v) for k, v in found.items()}
    print(json.dumps({"account": a.email, "endpoints_200": ok, "denied": denied,
                      "leaking_endpoints": len(leaks), "leaks": leaks}, indent=1, ensure_ascii=False))
    sys.exit(1 if leaks else 0)


if __name__ == "__main__":
    main()
