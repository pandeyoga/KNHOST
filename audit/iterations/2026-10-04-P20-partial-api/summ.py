"""Ringkas keluaran harness: python ../audit/iterations/2026-10-04-P20-partial-api/summ.py < out.txt"""
import json
import sys

t = sys.stdin.read()
i = t.find("[\n {")
try:
    for r in json.loads(t[i:t.rfind("]") + 1]):
        print("PASS" if r["pass"] else "FAIL", r["id"], r["invariant"][:95], "" if r["pass"] else r["detail"])
except Exception:  # noqa: BLE001
    print(t[-3000:])
print(t[-30:])
