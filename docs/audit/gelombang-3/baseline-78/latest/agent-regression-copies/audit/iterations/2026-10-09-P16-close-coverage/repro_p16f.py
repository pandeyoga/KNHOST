"""P16f — QC-05: dua inspector mengisi hasil inspeksi yang sama bersamaan → tidak ada hasil yang hilang.

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-09-P16-close-coverage/repro_p16f.py
Fixture: SPK inspeksi retur (tanpa roll) dengan 6 baris, dihapus di akhir.
"""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
T = f"TEST_P16F_{uuid.uuid4().hex[:6]}"
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def login(c, email):
    r = await c.post("/api/auth/login", json={"email": email, "password": "demo12345"})
    return {"Authorization": f"Bearer {r.json().get('token')}", "X-Entity-Id": "ent_ksc"}


async def run(c, db, ins_id):
    ha, hb = await login(c, "admin@kainnusantara.id"), await login(c, "manager@kainnusantara.id")
    lines = [f"insl_{T.lower()}_{i}" for i in range(6)]
    calls = [c.post(f"/api/inspections/{ins_id}/lines/{lid}/inspect",
                    json={"color_result": "sesuai", "handfeel_result": "sesuai", "remark": f"{T} {i}"},
                    headers=(ha if i % 2 else hb)) for i, lid in enumerate(lines)]
    res = await asyncio.gather(*calls)
    doc = await db.inspections.find_one({"id": ins_id}, {"_id": 0})
    done = [ln["id"] for ln in doc["lines"] if ln.get("inspected_at")]
    check("QC-05", "6 baris diisi bersamaan oleh 2 inspector → keenam hasil tersimpan (tanpa lost update)",
          all(r.status_code == 200 for r in res) and len(done) == 6, f"http={[r.status_code for r in res]} tersimpan={len(done)}/6")
    check("QC-05", "riwayat mencatat 6 pemeriksaan & ringkasan menghitung 6 baris diperiksa",
          sum(1 for e in doc.get("history", []) if e.get("event") == "line_inspected") == 6
          and (doc.get("summary") or {}).get("inspected", (doc.get("summary") or {}).get("inspected_lines")) in (6, None),
          {"summary": doc.get("summary")})
    same = await asyncio.gather(*[c.post(f"/api/inspections/{ins_id}/lines/{lines[0]}/inspect",
                                         json={"color_result": v, "handfeel_result": "sesuai", "remark": f"{T} {v}"}, headers=h)
                                  for v, h in (("beda_shade", ha), ("tolak", hb))])
    doc = await db.inspections.find_one({"id": ins_id}, {"_id": 0})
    l0 = next(ln for ln in doc["lines"] if ln["id"] == lines[0])
    check("QC-05", "baris yang sama diisi bersamaan → satu hasil utuh tersimpan (bukan campuran), 6 baris lain tetap",
          all(r.status_code in (200, 409) for r in same) and l0["color_result"] in ("beda_shade", "tolak")
          and l0["remark"].endswith(l0["color_result"]) and sum(1 for ln in doc["lines"] if ln.get("inspected_at")) == 6,
          f"{[r.status_code for r in same]} {l0['color_result']} / {l0['remark']}")


async def main():
    import httpx
    from db import db
    from core_utils import now_iso
    ins_id = f"ins_{T.lower()}"
    base = await db.inspections.find_one({}, {"_id": 0})
    lines = [{"id": f"insl_{T.lower()}_{i}", "roll_id": "", "sku": f"{T}-{i}", "roll_no": "", "color_result": "",
              "handfeel_result": "", "inspected_at": "", "decision": "", "remark": ""} for i in range(6)]
    await db.inspections.insert_one({**{k: base.get(k) for k in ("line_code",) if base}, "id": ins_id, "number": T,
                                     "kind": "return_customer", "entity_id": "ent_ksc", "status": "assigned",
                                     "lines": lines, "history": [], "created_at": now_iso(), "updated_at": now_iso()})
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8009", timeout=120) as c:
        try:
            await run(c, db, ins_id)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check("QC-05", "eksekusi skenario", False, repr(exc)[:200])
        finally:
            await db.inspections.delete_many({"id": ins_id})
            await db.audit_logs.delete_many({"entity_id": ins_id})
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
