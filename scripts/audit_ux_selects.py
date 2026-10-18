"""Uji filter dropdown (Radix combobox & select bawaan) per halaman: pilih opsi ke-2/ke-3 → daftar harus berubah.
  python scripts/audit_ux_selects.py <out_dir> view1,view2,..."""
import asyncio
import json
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, "/app/scripts")
from audit_ux_crawl import BASE, STATE_JS, login, settle  # noqa: E402


async def test_view(page, view):
    out = []
    await page.goto(f"{BASE}/?view={view}&entity=ent_ksc", wait_until="domcontentloaded")
    await settle(page, 2500)
    combos = page.locator("main button[role=combobox], main select")
    n = min(await combos.count(), 4)
    for i in range(n):
        el = combos.nth(i)
        try:
            if not await el.is_visible():
                continue
            tag = await el.evaluate("e => e.tagName")
            label = (await el.inner_text())[:40] if tag != "SELECT" else await el.evaluate("e => e.options[e.selectedIndex]?.text || ''")
            tid = await el.get_attribute("data-testid") or ""
            for idx in (1, 2):
                before = await page.evaluate(STATE_JS)
                if tag == "SELECT":
                    opts = await el.evaluate("e => [...e.options].map(o => o.text)")
                    if len(opts) <= idx:
                        break
                    await el.select_option(index=idx)
                    picked = opts[idx]
                else:
                    await el.click(force=True)
                    await page.wait_for_timeout(500)
                    options = page.locator("[role=option]")
                    if await options.count() <= idx:
                        await page.keyboard.press("Escape")
                        break
                    picked = (await options.nth(idx).inner_text())[:40]
                    await options.nth(idx).click(force=True)
                await page.wait_for_timeout(2200)
                after = await page.evaluate(STATE_JS)
                out.append({"view": view, "select": tid or label, "option": picked, "before": before["n"], "after": after["n"],
                            "changed": before["sig"] != after["sig"] or before["n"] != after["n"], "empty": after["empty"]})
            if tag == "SELECT":
                await el.select_option(index=0)
            else:
                await el.click(force=True)
                await page.wait_for_timeout(400)
                await page.locator("[role=option]").first.click(force=True)
            await page.wait_for_timeout(1200)
        except Exception as e:  # noqa: BLE001
            out.append({"view": view, "select": i, "error": str(e)[:80]})
            await page.keyboard.press("Escape")
    return out


async def main():
    out_dir, views = sys.argv[1], sys.argv[2].split(",")
    auth = login("admin@kainnusantara.id", "demo12345")
    res = []
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 1600, "height": 900})
        await ctx.add_init_script(f"localStorage.setItem('kn_token', {json.dumps(auth['token'])}); localStorage.setItem('kn_user', {json.dumps(json.dumps(auth['user']))});")
        page = await ctx.new_page()
        for v in views:
            r = await test_view(page, v)
            res += r
            for x in r:
                print(json.dumps(x, ensure_ascii=False), flush=True)
            json.dump(res, open(f"{out_dir}/selects.json", "w"), ensure_ascii=False, indent=1)
        await b.close()


asyncio.run(main())
