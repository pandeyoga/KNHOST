"""Verifikasi manual-otomatis temuan filter/search (satu filter per kali, reset di antaranya).
  python scripts/audit_ux_verify.py <out_dir>"""
import asyncio
import json
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, "/app/scripts")
from audit_ux_crawl import BASE, STATE_JS, login, settle  # noqa: E402

CASES = [
    ("operations", None, "Semua Gudang", "Bandung"),
    ("operations", None, "Semua Gudang", "Jakarta"),
    ("returns", None, "Semua Tipe", "Retur"),
    ("returns", None, "Semua Tipe", "Barang Sisa (BS)"),
    ("rnd-samples", None, "Semua jenis", "Handfeel"),
    ("rnd-samples", None, "Semua jenis", "Labdip"),
    ("sales", None, None, "Batik"),
    ("sales", None, None, "Knitting"),
    ("sales", None, None, "B"),
    ("design-requests", "Daftar", "Semua ronde", "Revisi ≥ 1"),
]


async def run(out):
    auth = login("admin@kainnusantara.id", "demo12345")
    res = []
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 1600, "height": 900})
        await ctx.add_init_script(f"localStorage.setItem('kn_token', {json.dumps(auth['token'])}); localStorage.setItem('kn_user', {json.dumps(json.dumps(auth['user']))});")
        page = await ctx.new_page()
        for view, tab, reset, chip in CASES:
            await page.goto(f"{BASE}/?view={view}&entity=ent_ksc", wait_until="domcontentloaded")
            await settle(page, 2500)
            if tab:
                await page.locator("main button", has_text=tab).first.click(force=True)
                await settle(page, 1500)
            before = await page.evaluate(STATE_JS)
            try:
                await page.get_by_role("button", name=chip, exact=True).first.click(force=True, timeout=5000)
            except Exception as e:  # noqa: BLE001
                print("tidak ketemu", view, chip, str(e)[:60], flush=True)
                continue
            await page.wait_for_timeout(2500)
            after = await page.evaluate(STATE_JS)
            name = f"{view}_{chip}".replace(" ", "_").replace("/", "_").replace("≥", "ge")
            await page.screenshot(path=f"{out}/verify_{name}.jpg", type="jpeg", quality=35)
            res.append({"view": view, "chip": chip, "before": before["n"], "after": after["n"], "changed": before["sig"] != after["sig"],
                        "before_sig": before["sig"][:120], "after_sig": after["sig"][:120]})
            print(json.dumps(res[-1], ensure_ascii=False), flush=True)
        await page.goto(f"{BASE}/?view=operations&entity=ent_ksc", wait_until="domcontentloaded")
        await settle(page, 2500)
        tabs = await page.evaluate("""() => [...document.querySelectorAll('main [data-testid^="wms-tab-"], main [data-testid^="hub-tab-"]')].map(e => ({t: e.getAttribute('data-testid'), l: e.innerText.trim(), y: Math.round(e.getBoundingClientRect().top), vis: e.getBoundingClientRect().height > 0}))""")
        print(json.dumps(tabs, ensure_ascii=False))
        await b.close()
    json.dump(res, open(f"{out}/verify.json", "w"), ensure_ascii=False, indent=1)


asyncio.run(run(sys.argv[1]))
