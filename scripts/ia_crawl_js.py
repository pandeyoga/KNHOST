JS_COLLECT = r"""
() => {
  const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const inHub = (el) => !!el.closest('[data-testid^="hub-tabs-"]');
  const inNav = (el) => !!el.closest('aside, nav, [data-testid="sidebar"], header');
  const sel = '[role="tab"], .tab-pill, .tab-button, .seg-btn, [data-testid*="-tab-"], [data-testid$="-tab"]';
  const out = [];
  document.querySelectorAll(sel).forEach((el) => {
    if (!vis(el) || inHub(el) || inNav(el)) return;
    const t = (el.innerText || "").replace(/\s+/g, " ").trim().slice(0, 40);
    if (t && !out.some((o) => o.t === t)) out.push({ t, id: el.getAttribute("data-testid") || "" });
  });
  const heads = [...document.querySelectorAll('main h1, main h2, main h3, [data-testid="page-title"]')]
    .filter(vis).map((h) => h.innerText.trim().slice(0, 50)).filter(Boolean).slice(0, 8);
  return { tabs: out.slice(0, 25), heads };
}
"""
