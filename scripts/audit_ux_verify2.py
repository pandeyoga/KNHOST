"""Cek terarah: menu Pesanan/Pesanan Khusus untuk sales, jumlah tab status PO vs isi.
  python scripts/audit_ux_verify2.py <out_dir>"""
import asyncio
import json
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, "/app/scripts")
from audit_ux_crawl import BASE, STATE_JS, login, settle  # noqa: E402


async def ctx_for(b, email):
    auth = login(email, "demo12345")
    ctx = await b.new_context(viewport={"width": 1600, "height": 900})
    await ctx.add_init_script(f"localStorage.setItem('kn_token', {json.dumps(auth['token'])}); localStorage.setItem('kn_user', {json.dumps(json.dumps(auth['user']))});")
    return ctx


async def main(out):
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-sandbox"])
        page = await (await ctx_for(b, "sales@kainnusantara.id")).new_page()
        for nav in ("orders", "special-orders"):
            await page.goto(f"{BASE}/?view=sales", wait_until="domcontentloaded")
            await settle(page, 3000)
            sb = await page.evaluate("() => { const a = document.querySelector('aside'); return a ? Math.round(a.getBoundingClientRect().width) : -1; }")
            await page.goto(f"{BASE}/?view={nav}", wait_until="domcontentloaded")
            await settle(page, 3000)
            info = {"sidebar_width_on_pos": sb}
            url = page.url
            title = await page.evaluate("() => (document.querySelector('header h1') || {}).innerText || ''")
            await page.screenshot(path=f"{out}/sales_{nav}.jpg", type="jpeg", quality=35)
            print(nav, json.dumps(info, ensure_ascii=False)[:200], "→", url, "|", title, flush=True)
        page = await (await ctx_for(b, "admin@kainnusantara.id")).new_page()
        await page.goto(f"{BASE}/?view=purchasing&entity=ent_ksc", wait_until="domcontentloaded")
        await settle(page, 3000)
        for lab in ("Menunggu / Proses Terima", "Selesai"):
            await page.get_by_role("button", name=lab).first.click(force=True)
            await page.wait_for_timeout(2500)
            rows = await page.evaluate("""() => [...document.querySelectorAll('main tbody tr')].filter(r => r.getBoundingClientRect().height > 1).map(r => r.innerText.replace(/\\s+/g, ' ').slice(0, 90))""")
            print(lab, len(rows), json.dumps(rows, ensure_ascii=False)[:900], flush=True)
            await page.screenshot(path=f"{out}/po_tab_{lab.split()[0]}.jpg", type="jpeg", quality=35)
        await b.close()


asyncio.run(main(sys.argv[1]))
