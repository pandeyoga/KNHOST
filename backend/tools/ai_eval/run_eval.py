"""Tanya KN F5 — pengukur set evaluasi.

  python tools/ai_eval/run_eval.py --mode engine   # tanpa kunci: argumen harapan dijalankan langsung ke mesin
  python tools/ai_eval/run_eval.py --mode model    # butuh kunci OpenAI + ai.enabled: pilihan tool oleh model

Target §9: pemilihan tool ≥ 90%, argumen benar ≥ 90%, pemeriksa angka ≥ 98%, penolakan hak akses 100%.
"""
import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from db import db  # noqa: E402
from services import ai_tools  # noqa: E402
from services.ai_schedules import ctx_for  # noqa: E402

HERE = Path(__file__).parent
EMAIL = {"admin": "admin@kainnusantara.id", "sales": "sales@kainnusantara.id", "finance": "finance@kainnusantara.id",
         "warehouse_admin": "warehouse@kainnusantara.id", "sales_admin": "salesadmin@kainnusantara.id", "md": "md@kainnusantara.id"}
KEY_ARGS = ("metrics", "group_by", "record_type", "report", "time_grain", "compare")


async def _user(role):
    u = await db.users.find_one({"email": EMAIL[role]}, {"_id": 0, "password": 0, "password_hash": 0})
    return u, await ctx_for(u, u.get("home_entity_id") or "ent_ksc", False)


def _judge_engine(q, res):
    if q["expect"] == "denied":
        return bool(set(q["denied_metrics"]) & set(res.get("denied") or [])) or bool(res.get("error"))
    return not res.get("error")


async def run_engine(qs):
    rows = []
    for q in qs:
        if not q["expected"]:
            continue
        user, ctx = await _user(q["role"])
        t0 = time.perf_counter()
        res = await ai_tools.execute(q["expected"]["tool"], q["expected"]["args"], user, ctx, "eval")
        rows.append({"id": q["id"], "category": q["category"], "ok": _judge_engine(q, res), "error": res.get("error"),
                     "ms": int((time.perf_counter() - t0) * 1000)})
    return rows


def _args_match(exp, got):
    return all(sorted(map(str, exp.get(k) or [])) == sorted(map(str, got.get(k) or [])) if isinstance(exp.get(k), list)
               else exp.get(k) == got.get(k) for k in KEY_ARGS if k in exp)


async def run_model(qs):
    from services.ai_chat_service import chat_events
    rows = []
    for q in qs:
        user, ctx = await _user(q["role"])
        tools, text, ver, t0 = [], "", None, time.perf_counter()
        async for ev in chat_events(q["question"], None, False, user, ctx):
            if ev["type"] == "tool":
                tools.append(ev)
            elif ev["type"] == "delta":
                text += ev["text"]
            elif ev["type"] == "done":
                ver = ev.get("verification")
        exp, first = q["expected"], (tools[0] if tools else None)
        tool_ok = (first is None) if exp is None else bool(first and first["name"] == exp["tool"])
        args_ok = tool_ok and (exp is None or _args_match(exp["args"], first["arguments"]))
        rows.append({"id": q["id"], "category": q["category"], "tool_ok": tool_ok, "args_ok": args_ok,
                     "numbers_ok": (ver or {}).get("ok", True), "tools": [t["name"] for t in tools],
                     "ms": int((time.perf_counter() - t0) * 1000), "answer": text[:300]})
    return rows


def _pct(rows, key):
    return round(sum(1 for r in rows if r.get(key)) / len(rows) * 100, 1) if rows else None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("engine", "model"), default="engine")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    qs = json.loads((HERE / "questions_v1.json").read_text())["questions"]
    qs = qs[: a.limit] if a.limit else qs
    rows = await (run_engine(qs) if a.mode == "engine" else run_model(qs))
    ms = sorted(r["ms"] for r in rows)
    summary = {"mode": a.mode, "n": len(rows), "p50_ms": ms[len(ms) // 2] if ms else None}
    if a.mode == "engine":
        summary["args_valid_pct"] = _pct(rows, "ok")
        summary["access_denied_pct"] = _pct([r for r in rows if r["category"] == "hak_akses"], "ok")
    else:
        summary.update(tool_pct=_pct(rows, "tool_ok"), args_pct=_pct(rows, "args_ok"), numbers_pct=_pct(rows, "numbers_ok"))
    out = HERE / "reports" / f"{a.mode}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))
    for r in rows:
        if not r.get("ok", r.get("tool_ok")):
            print("  GAGAL", r["id"], r["category"], r.get("error") or r.get("tools"))
    print("laporan:", out)


if __name__ == "__main__":
    asyncio.run(main())
