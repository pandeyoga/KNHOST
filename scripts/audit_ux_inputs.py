"""Cek ulang halaman yang tercatat 'tanpa search': daftar semua input teks terlihat (placeholder apa pun).
  python scripts/audit_ux_inputs.py <out_json> view1,view2,..."""
import asyncio
import json
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, "/app/scripts")
from audit_ux_crawl import BASE, login, settle  # noqa: E402

JS = r"""() => [...(document.querySelector('main') || document.body).querySelectorAll('input:not([type=checkbox]):not([type=radio]):not([type=hidden]):not([type=file]):not([type=date]):not([type=number])')]
  .filter(i => i.getBoundingClientRect().height > 1 && !i.closest('[role=dialog]') && !i.closest('form'))
  .map(i => ({ph: i.placeholder || '', w: Math.round(i.getBoundingClientRect().width), testid: i.getAttribute('data-testid') || ''}))"""


async def main():
    out, views = sys.argv[1], sys.argv[2].split(",")
    auth = login("admin@kainnusantara.id", "demo12345")
    res, q = {}, asyncio.Queue()
    for v in views:
        q.put_nowait(v)
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-sandbox"])

        async def worker():
            ctx = await b.new_context(viewport={"width": 1600, "height": 900})
            await ctx.add_init_script(f"localStorage.setItem('kn_token', {json.dumps(auth['token'])}); localStorage.setItem('kn_user', {json.dumps(json.dumps(auth['user']))});")
            page = await ctx.new_page()
            while not q.empty():
                v = q.get_nowait()
                try:
                    await page.goto(f"{BASE}/?view={v}&entity=ent_ksc", wait_until="domcontentloaded", timeout=40000)
                    await settle(page, 2000)
                    res[v] = await page.evaluate(JS)
                except Exception as e:  # noqa: BLE001
                    res[v] = {"error": str(e)[:80]}
                print(v, json.dumps(res[v], ensure_ascii=False)[:200], flush=True)
            await ctx.close()
        await asyncio.gather(*[worker() for _ in range(4)])
        await b.close()
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)


asyncio.run(main())
