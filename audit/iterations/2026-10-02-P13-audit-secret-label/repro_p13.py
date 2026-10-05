"""P13 — GN-14, UX-03 — regression invariant (in-process + HTTP lokal + statis, data sintetis).

Usage: cd /app/backend && python ../audit/iterations/2026-10-02-P13-audit-secret-label/repro_p13.py [repo_root]
HTTP memakai backend lokal http://localhost:8001 (kode yang sedang berjalan). Nilai secret TIDAK dicetak.
"""
import asyncio
import json
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("..").resolve()
results = []
T = f"audit_p13_{uuid.uuid4().hex[:6]}"


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def main():
    from db import db
    import dependencies as deps

    # ── GN-14 helper audit: before/after/diff/redaksi/actor_id ───────────────
    try:
        from request_context import set_actor
        set_actor({"id": f"{T}_u", "name": "Audit P13", "role": "admin"})
        await deps.audit("Audit P13", "gl_account_updated", "gl_account", f"{T}_acc",
                         {"name": "Baru", "api_key": "x" * 20, "nested": {"password": "rahasia"}},
                         before={"name": "Lama", "api_key": "y" * 20}, source="routers/gl.update")
        row = await db.audit_logs.find_one({"entity_id": f"{T}_acc"}, {"_id": 0})
        check("GN-14", "audit menyimpan before & diff field yang berubah",
              row and row["before"] and row["before"].get("name") == "Lama"
              and any(d["field"] == "name" and d["from"] == "Lama" and d["to"] == "Baru" for d in row.get("diff") or []),
              {k: row.get(k) for k in ("before", "diff")} if row else None)
        blob = json.dumps(row, default=str)
        check("GN-14", "secret di before/after diredaksi", "rahasia" not in blob and "x" * 20 not in blob and "y" * 20 not in blob)
        check("GN-14", "actor_id, source & content_hash tercatat",
              row.get("actor_id") == f"{T}_u" and row.get("source") == "routers/gl.update" and len(row.get("content_hash") or "") == 64,
              {k: row.get(k) for k in ("actor_id", "source")})
    except Exception as exc:  # noqa: BLE001
        check("GN-14", "helper audit mendukung before/source", False, repr(exc)[:200])

    # ── GN-14 HTTP: endpoint keuangan mencatat nilai sebelum ───────────────
    try:
        import os
        import httpx
        if os.environ.get("SKIP_HTTP"):
            raise RuntimeError("HTTP dilewati (baseline HEAD: server yang berjalan bukan kode HEAD)")
        async with httpx.AsyncClient(base_url="http://localhost:8001", timeout=30) as c:
            tok = (await c.post("/api/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})).json()
            tok = tok.get("token") or tok.get("access_token") or ""
            h = {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}
            code = f"9-{uuid.uuid4().hex[:4].upper()}"
            r = await c.post("/api/gl/accounts", json={"code": code, "name": f"{T} Lama", "type": "expense"}, headers=h)
            r2 = await c.patch(f"/api/gl/accounts/{code}", json={"name": f"{T} Baru"}, headers=h)
            row = await db.audit_logs.find_one({"action": "gl_account_updated", "entity_id": code}, {"_id": 0},
                                               sort=[("timestamp", -1)])
            check("GN-14", "PATCH akun GL: before.name lama, after.name baru, diff",
                  r.status_code == 200 and r2.status_code == 200 and row
                  and (row.get("before") or {}).get("name") == f"{T} Lama" and (row.get("after") or {}).get("name") == f"{T} Baru",
                  f"{r.status_code}/{r2.status_code} before={(row or {}).get('before')}")
            await c.delete(f"/api/gl/accounts/{code}", headers=h)
            row = await db.audit_logs.find_one({"action": "gl_account_deleted", "entity_id": code}, {"_id": 0})
            check("GN-14", "hapus akun GL menyimpan snapshot sebelum", row and (row.get("before") or {}).get("code") == code,
                  (row or {}).get("before"))
            await db.audit_logs.delete_many({"entity_id": code})
            await db.gl_accounts.delete_many({"code": code})
    except Exception as exc:  # noqa: BLE001
        check("GN-14", "HTTP akun GL", False, repr(exc)[:200])

    # ── GN-14 repo: file token tidak ada & di-ignore; pemindai secret tersedia ─
    toks = [p for p in (".tok", ".tok_admin", ".tok_mgr", "memory/.tok_admin") if (ROOT / p).exists()]
    check("GN-14", "file token sesi tidak ada di pohon repo", not toks, toks)
    gi = (ROOT / ".gitignore").read_text() if (ROOT / ".gitignore").exists() else ""
    check("GN-14", ".gitignore menolak .tok*", ".tok" in gi and ".tok_*" in gi)
    check("GN-14", "pemindai secret tersedia", (ROOT / "scripts/guardrails/verify_no_secrets.py").exists())

    # ── UX-03 — panel biaya OCR ────────────────────────────────────────────
    src = (ROOT / "frontend/src/features/wms/grn/GrnOcrUsagePanel.jsx").read_text()
    check("UX-03", "kolom Badan usaha tidak merender ID mentah", not re.search(r">\{r\.entity_id\}<", src))
    check("UX-03", "memakai resolver label entitas + fallback", "entityShortById" in src and "tidak dikenal" in src)

    await db.audit_logs.delete_many({"entity_id": f"{T}_acc"})
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
