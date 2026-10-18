"""Audit UX menyeluruh (read-only): setiap view × tab → profil pola (judul, KPI, search, tab, filter, tabel, paginasi)
+ uji fungsi filter/search sungguhan. Tidak mengubah data (hanya klik tab/filter/ketik search).
  python scripts/audit_ux_crawl.py <role_email> <password> <out_dir> [workers]
"""
import asyncio
import json
import os
import sys

import requests
from playwright.async_api import async_playwright

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].strip()
VIEWS = json.load(open("/app/docs/audit/ia/views.json"))

PROFILE_JS = r"""
() => {
  const main = document.querySelector('main') || document.body;
  const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 1 && r.height > 1 && getComputedStyle(el).visibility !== 'hidden'; };
  const inDialog = (el) => !!el.closest('[role="dialog"]');
  const sig = (el) => (el.className && typeof el.className === 'string' ? el.className : '').split(/\s+/).filter(c => /^(rounded|border|bg-|h-|py-|px-|text-|shadow|w-|max-w|flex-1)/.test(c)).sort().join(' ');
  const top = main.getBoundingClientRect().top;
  const txt = (el) => (el.innerText || el.value || '').trim().replace(/\s+/g, ' ').slice(0, 60);
  const searches = [...main.querySelectorAll('input')].filter(i => vis(i) && !inDialog(i) && (i.type === 'search' || /cari|search|scan/i.test(i.placeholder || '')))
    .map(i => { const r = i.getBoundingClientRect(); return { ph: i.placeholder, testid: i.getAttribute('data-testid') || '', y: Math.round(r.top - top), x: Math.round(r.left), w: Math.round(r.width),
      sig: sig(i) + ' | ' + sig(i.parentElement), icon: !!(i.parentElement && i.parentElement.querySelector('svg')) }; });
  const tabEls = [...main.querySelectorAll('[role="tab"], [data-testid*="-tab-"], [data-testid^="hub-tab-"]')].filter(e => vis(e) && !inDialog(e));
  const groups = new Map();
  tabEls.forEach(e => { const p = e.closest('[role="tablist"], [data-testid^="hub-tabs-"]') || e.parentElement; if (!groups.has(p)) groups.set(p, []); groups.get(p).push(e); });
  const tabs = [...groups.entries()].map(([p, els]) => ({ y: Math.round(p.getBoundingClientRect().top - top), hub: !!(p.getAttribute('data-testid') || '').startsWith('hub-tabs-'),
    labels: els.map(txt), testids: els.map(e => e.getAttribute('data-testid') || ''), sig: sig(els[0]) }));
  const tabSet = new Set(tabEls);
  const btnGroups = new Map();
  [...main.querySelectorAll('button')].filter(b => vis(b) && !inDialog(b) && !tabSet.has(b) && /rounded-full|chip|pill/.test(b.className || '') && txt(b).length < 40)
    .forEach(b => { const p = b.parentElement; if (!btnGroups.has(p)) btnGroups.set(p, []); btnGroups.get(p).push(b); });
  const chips = [...btnGroups.entries()].filter(([p, bs]) => bs.length >= 2).map(([p, bs]) => ({ y: Math.round(p.getBoundingClientRect().top - top), labels: bs.map(txt), testids: bs.map(b => b.getAttribute('data-testid') || '') }));
  const selects = [...main.querySelectorAll('select, button[role="combobox"]')].filter(e => vis(e) && !inDialog(e)).map(e => ({ testid: e.getAttribute('data-testid') || '', label: txt(e), y: Math.round(e.getBoundingClientRect().top - top) }));
  const dates = [...main.querySelectorAll('input[type="date"], input[type="month"]')].filter(e => vis(e) && !inDialog(e)).length;
  const rows = [...main.querySelectorAll('tbody tr')].filter(r => vis(r) && !inDialog(r));
  const listRows = [...main.querySelectorAll('[data-testid*="-row-"], [data-testid*="-card-"], [data-testid*="-item-"]')].filter(r => vis(r) && !inDialog(r));
  const big = [...main.querySelectorAll('p, span, div, h3, strong')].filter(e => vis(e) && !inDialog(e) && e.children.length === 0 && parseFloat(getComputedStyle(e).fontSize) >= 20 && /^(Rp\s?)?[\d.,]+(\s?(%|kg|yard|m|roll))?$/.test(txt(e)));
  const kpis = big.map(e => { const card = e.closest('[class*="rounded"]'); return { val: txt(e), label: card ? txt(card).replace(txt(e), '').slice(0, 50) : '' }; }).slice(0, 12);
  const body = main.innerText || '';
  const pager = /Per halaman|Hal\s+\d+\s*\/\s*\d+|Sebelumnya|Berikutnya|Muat lebih/.test(body);
  const h = document.querySelector('header h1, header [data-testid="topbar-title"]');
  const heads = [...main.querySelectorAll('h1, h2, h3')].filter(vis).slice(0, 6).map(txt);
  const empty = /Belum ada|Tidak ada data|Tidak ada .* ditemukan|Kosong|tidak ditemukan/i.test(body);
  const rowSig = (rows.length ? rows : listRows).slice(0, 3).map(txt).join(' || ');
  return { title: h ? txt(h) : '', heads, searches, tabs, chips, selects, dates, rows: rows.length, listRows: listRows.length, kpis, pager, empty, rowSig,
           pageHeaderCard: !!main.querySelector('[data-testid$="-page-header"], .page-header') };
}
"""

STATE_JS = r"""() => { const m = document.querySelector('main') || document.body; const rows = [...m.querySelectorAll('tbody tr, [data-testid*="-row-"], [data-testid*="-card-"]')].filter(r => r.getBoundingClientRect().height > 1 && !r.closest('[role=dialog]'));
  return { n: rows.length, sig: rows.slice(0, 4).map(r => (r.innerText || '').trim().slice(0, 40)).join('|'), empty: /Belum ada|Tidak ada|tidak ditemukan|Kosong/i.test(m.innerText || '') }; }"""


def login(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    r.raise_for_status()
    return r.json()


async def settle(page, ms=1800):
    try:
        await page.wait_for_load_state("networkidle", timeout=6000)
    except Exception:  # noqa: BLE001
        pass
    await page.wait_for_timeout(ms)
    last = None
    for _ in range(8):  # tunggu daftar stabil (data async)
        cur = await page.evaluate(STATE_JS)
        if last and cur == last and (cur["n"] or cur["empty"]):
            break
        last = cur
        await page.wait_for_timeout(900)


async def state(page):
    return await page.evaluate(STATE_JS)


async def test_filters(page, prof):
    out = []
    for g in prof["chips"][:4]:
        res = []
        for i, lab in enumerate(g["labels"][:8]):
            try:
                loc = page.locator("main button", has_text=lab).first
                before = await state(page)
                await loc.click(timeout=3000)
                await page.wait_for_timeout(1800)
                after = await state(page)
                res.append({"label": lab, "before": before["n"], "after": after["n"], "changed": before["sig"] != after["sig"] or before["n"] != after["n"], "empty": after["empty"]})
            except Exception as e:  # noqa: BLE001
                res.append({"label": lab, "error": str(e)[:80]})
        try:
            await page.locator("main button", has_text=g["labels"][0]).first.click(timeout=2000)
            await page.wait_for_timeout(800)
        except Exception:  # noqa: BLE001
            pass
        out.append({"group": g["labels"][:8], "results": res})
    return out


async def test_search(page, prof):
    out = []
    for s in prof["searches"][:2]:
        try:
            loc = page.locator("main").get_by_placeholder(s["ph"], exact=True).first
            before = await state(page)
            await loc.fill("zzqxw9")
            await page.wait_for_timeout(2200)
            junk = await state(page)
            await loc.fill("")
            await page.wait_for_timeout(1200)
            out.append({"ph": s["ph"], "before": before["n"], "junk": junk["n"], "junk_empty": junk["empty"],
                        "works": (before["n"] > 0 and (junk["n"] < before["n"] or junk["empty"])) if before["n"] else None})
        except Exception as e:  # noqa: BLE001
            out.append({"ph": s["ph"], "error": str(e)[:80]})
    return out


async def audit_view(ctx, view, out_dir, entity):
    page = await ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)[:160]))
    rec = {"view": view, "states": []}
    try:
        await page.goto(f"{BASE}/?view={view}&entity={entity}", wait_until="domcontentloaded", timeout=45000)
        await settle(page, 2500)
        prof = await page.evaluate(PROFILE_JS)
        await page.screenshot(path=f"{out_dir}/shots/{view}.jpg", type="jpeg", quality=35, full_page=False)
        prof["filters"] = await test_filters(page, prof)
        prof["search_test"] = await test_search(page, prof)
        rec["states"].append({"tab": "", **prof})
        inner = [g for g in prof["tabs"] if not g["hub"]]
        for g in inner[:2]:
            for lab, tid in list(zip(g["labels"], g["testids"]))[:12]:
                try:
                    sel = f'[data-testid="{tid}"]' if tid else None
                    loc = page.locator(sel).first if sel else page.locator("main [role=tab]", has_text=lab).first
                    await loc.scroll_into_view_if_needed(timeout=3000)
                    await loc.click(timeout=4000, force=True)
                    await settle(page, 1500)
                    p2 = await page.evaluate(PROFILE_JS)
                    p2["filters"] = await test_filters(page, p2)
                    p2["search_test"] = await test_search(page, p2)
                    safe = (tid or lab).replace("/", "_")[:60]
                    await page.screenshot(path=f"{out_dir}/shots/{view}__{safe}.jpg", type="jpeg", quality=30, full_page=False)
                    rec["states"].append({"tab": lab, "tab_testid": tid, **p2})
                except Exception as e:  # noqa: BLE001
                    rec["states"].append({"tab": lab, "error": str(e)[:100]})
    except Exception as e:  # noqa: BLE001
        rec["error"] = str(e)[:200]
    rec["pageerrors"] = errs[:5]
    await page.close()
    return rec


async def discover_views(ctx, entity):
    """Semua view yang terlihat peran ini: item sidebar + tab hub di halaman tujuannya."""
    page = await ctx.new_page()
    await page.goto(f"{BASE}/?entity={entity}", wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(4000)
    for t in await page.locator('[data-testid^="nav-group-toggle-"]').all():
        try:
            if (await t.get_attribute("aria-expanded")) != "true":
                await t.click(timeout=2000)
                await page.wait_for_timeout(250)
        except Exception:  # noqa: BLE001
            pass
    ids = await page.evaluate("""() => [...document.querySelectorAll('aside [data-testid^="nav-"]')].map(e => e.getAttribute('data-testid'))
        .filter(t => !/^nav-(group|fav)/.test(t))""")
    views, menu = [], []
    for tid in dict.fromkeys(ids):
        try:
            await page.locator(f'[data-testid="{tid}"]').first.click(timeout=3000, force=True)
            await page.wait_for_timeout(1800)
            v = await page.evaluate("() => new URLSearchParams(location.search).get('view')")
            hubs = await page.evaluate("""() => [...document.querySelectorAll('[data-testid^="hub-tab-"]')].map(e => e.getAttribute('data-testid').slice(8))""")
            menu.append({"nav": tid, "view": v, "hub_tabs": hubs})
            for x in [v] + hubs:
                if x and x not in views:
                    views.append(x)
        except Exception as e:  # noqa: BLE001
            menu.append({"nav": tid, "error": str(e)[:80]})
    await page.close()
    return views, menu


async def main():
    email, pw, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    only = sys.argv[5].split(",") if len(sys.argv) > 5 else None
    os.makedirs(f"{out_dir}/shots", exist_ok=True)
    auth = login(email, pw)
    entity = auth["user"].get("home_entity_id") or "ent_ksc"
    results, q = [], asyncio.Queue()
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        init = f"localStorage.setItem('kn_token', {json.dumps(auth['token'])}); localStorage.setItem('kn_user', {json.dumps(json.dumps(auth['user']))});"
        if only == ["MENU"]:
            c0 = await browser.new_context(viewport={"width": 1600, "height": 900})
            await c0.add_init_script(init)
            views, menu = await discover_views(c0, entity)
            json.dump(menu, open(f"{out_dir}/menu.json", "w"), ensure_ascii=False, indent=1)
            print(f"menu: {len(menu)} item, {len(views)} view", flush=True)
            await c0.close()
        else:
            views = only or VIEWS
        for v in views:
            q.put_nowait(v)

        async def worker():
            ctx = await browser.new_context(viewport={"width": 1600, "height": 900})
            await ctx.add_init_script(f"localStorage.setItem('kn_token', {json.dumps(auth['token'])}); localStorage.setItem('kn_user', {json.dumps(json.dumps(auth['user']))});")
            while not q.empty():
                v = q.get_nowait()
                r = await audit_view(ctx, v, out_dir, entity)
                results.append(r)
                print(f"[{len(results)}/{len(views)}] {v} states={len(r['states'])} {r.get('error', '')}", flush=True)
                json.dump(results, open(f"{out_dir}/crawl.json", "w"), ensure_ascii=False)
            await ctx.close()
        await asyncio.gather(*[worker() for _ in range(workers)])
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
