"""Seed data CONTOH biaya AI 30 hari (demo: True) untuk Halaman Biaya AI. Tidak dihitung ke anggaran.
Jalankan: cd /app/backend && python ../scripts/seed_ai_usage_demo.py   ·   hapus: ... --clear
"""
import asyncio
import os
import random
import sys
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))
from core_utils import new_id  # noqa: E402
from db import db  # noqa: E402
from services import ai_cost  # noqa: E402
from services.analytics_time import now_wib  # noqa: E402

EMAILS = ["admin@kainnusantara.id", "manager@kainnusantara.id", "sales@kainnusantara.id", "finance@kainnusantara.id",
          "salesadmin@kainnusantara.id"]


async def main():
    await db.ai_usage_log.delete_many({"demo": True})
    if "--clear" in sys.argv:
        print("Data contoh biaya AI dihapus.")
        return
    users = [u async for u in db.users.find({"email": {"$in": EMAILS}}, {"_id": 0, "id": 1})]
    rnd, now, docs = random.Random(42), now_wib(), []
    for back in range(30):
        day = now - timedelta(days=back)
        for _ in range(rnd.randint(3, 14) if day.weekday() < 5 else rnd.randint(0, 3)):
            feature, model = rnd.choices([("bi_chat", "gpt-6-sol"), ("bi_template", "gpt-6-luna"), ("bi_template", "gpt-6-sol")],
                                         weights=[6, 3, 1])[0]
            usage = {"input_tokens": rnd.randint(6000, 22000), "output_tokens": rnd.randint(300, 1800)}
            usage["cached_tokens"] = int(usage["input_tokens"] * rnd.uniform(.4, .8))
            at = day.replace(hour=rnd.randint(8, 18), minute=rnd.randint(0, 59))
            docs.append({"id": new_id("aiu"), "feature": feature, "model": model, "user_id": rnd.choice(users)["id"] if users else "",
                         "usage": usage, "cost_usd": ai_cost.cost_usd(model, usage), "created_at": at.isoformat(), "demo": True})
        if day.weekday() < 5:
            u = {"input_tokens": 15000, "output_tokens": 16}
            docs.append({"id": new_id("aiu"), "feature": "bi_prewarm", "model": "gpt-6-sol", "usage": u, "demo": True,
                         "cost_usd": ai_cost.cost_usd("gpt-6-sol", u), "created_at": day.replace(hour=6, minute=55).isoformat()})
    if docs:
        await db.ai_usage_log.insert_many(docs)
    print(f"{len(docs)} baris contoh biaya AI dibuat (demo: True).")


if __name__ == "__main__":
    asyncio.run(main())
