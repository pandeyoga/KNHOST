JS_SCAN = r"""
() => {
  const root = document.querySelector('main') || document.body;
  const txt = root.innerText || "";
  const pats = [/\bNaN\b/, /\bundefined\b/, /\[object Object\]/, /Invalid Date/, /\bnull\b/, /TEST_|\bTEST\b|iter1\d\d/,
                /BELUM tersambung/i, /Rp\s?-?NaN/, /Infinity/, /Gagal memuat|gagal memuat|Terjadi kesalahan|Error:|Request failed|status code \d{3}/,
                /Not Found|Internal Server Error|Forbidden/];
  const hits = [];
  pats.forEach((p) => { const m = txt.match(p); if (m) { const i = txt.indexOf(m[0]); hits.push(txt.slice(Math.max(0, i - 50), i + 60).replace(/\s+/g, " ")); } });
  const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const ovf = [...root.querySelectorAll('button, th, td, h1, h2, h3, .kpi-card, [data-testid*="kpi"], [data-testid*="card"]')]
    .filter((el) => vis(el) && el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflow === 'visible' && getComputedStyle(el).whiteSpace === 'nowrap')
    .slice(0, 3).map((el) => (el.getAttribute('data-testid') || el.tagName) + ':' + (el.innerText || '').slice(0, 30));
  const unstyled = [...root.querySelectorAll('button')].filter((b) => vis(b) && getComputedStyle(b).backgroundColor === 'rgb(239, 239, 239)').length;
  const tabs = [...document.querySelectorAll('[role="tab"], .tab-pill, .tab-button, [data-testid*="-tab-"]')]
    .filter((el) => vis(el) && !el.closest('[data-testid^="hub-tabs-"], aside, header')).slice(0, 12)
    .map((el) => el.getAttribute('data-testid') || '');
  return { hits, ovf, unstyled, tabs };
}
"""
