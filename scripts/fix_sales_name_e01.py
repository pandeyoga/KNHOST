"""KN-E01 — perbaiki data lama: sales_name pesanan yang terisi tetap "Ayu Marketing".

Sumber nama yang benar: PIC sales_team → pembuat pesanan (created_by) → dibiarkan.
Jalankan:  cd /app/backend && python ../scripts/fix_sales_name_e01.py [--apply]
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))
from db import db  # noqa: E402

LEGACY = "Ayu Marketing"


async def main(apply: bool) -> None:
    users = {u["id"]: u.get("name", "") async for u in db.users.find({}, {"_id": 0, "id": 1, "name": 1})}
    ayu_ids = {uid for uid, n in users.items() if n == LEGACY}
    fixed = skipped = 0
    async for o in db.sales_orders.find({"sales_name": LEGACY},
                                        {"_id": 0, "id": 1, "number": 1, "created_by": 1, "sales_team": 1}):
        pic = next((m for m in o.get("sales_team") or [] if m.get("role") == "pic"), None)
        if (pic and pic.get("sales_id") in ayu_ids) or (not pic and o.get("created_by") in ayu_ids):
            skipped += 1
            continue
        name = (pic or {}).get("name") or users.get(o.get("created_by") or "", "")
        if not name or name == LEGACY:
            skipped += 1
            continue
        print(f"{o.get('number')}: {LEGACY} → {name}")
        if apply:
            await db.sales_orders.update_one({"id": o["id"]}, {"$set": {"sales_name": name}})
        fixed += 1
    print(f"{'DIPERBAIKI' if apply else 'AKAN DIPERBAIKI (dry-run)'}: {fixed} · dilewati: {skipped}")


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv))
