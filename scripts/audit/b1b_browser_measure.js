/*
 * Audit B1b — pengukur layar di peramban (HANYA BACA; tidak menekan tombol simpan apa pun).
 *
 * Cara pakai (konsol / alat JS peramban, origin aplikasi, mis. http://localhost:3063):
 *   1. Tempel isi berkas ini sekali (atau simpan ke localStorage lalu `(0,eval)(localStorage.getItem(KEY))` tiap muat
 *      ulang — B1b memakai kunci `b1b_fn` dan MENGHAPUSNYA di akhir audit).
 *   2. Ganti akun (opsional): `window.__b1bGo = '<url tujuan>'; await __b1bLogin(email, sandi)` — login lewat API dengan
 *      cookie (sama seperti layar login), PT aktif = PT bawaan akun (catatan UI-39). Sandi demo TIDAK ditulis di sini.
 *   3. Buka `?view=<view>` lalu `await __s({want:'<view>'})` (ringkas, desktop), `await __h({want})` (390 px),
 *      `await __hp()` (aplikasi HP: klik tiap tab bawah lalu ukur), `await __dlg({})` (pop-up terbuka → ukur → Esc).
 *
 * Yang diukur: menunggu sampai tidak ada "Memuat…"/spinner DAN jaringan API diam ≥1,5 s (`quiet`); porsi teks < 12 px,
 * ukuran huruf terkecil, jumlah tombol di bawah 24/32/36/44/48 px (tinggi ATAU lebar), tinggi & huruf isian, kotak cari,
 * chip saringan (`.filter-chip`), pager ("Menampilkan n"), tombol ekspor, tabel mentah & kolom yang bisa diurut, id mentah,
 * data uji (TEST_/UJI-/iter_), teks galat, keadaan kosong, "kosong palsu" (teks kosong yang tampil SELAMA memuat),
 * istilah Inggris (daftar pendek), geser mendatar dokumen. Angka = elemen yang terlihat di <main> (desktop) atau di
 * wadah aplikasi HP.
 */
window.__b1b = async function (o) {
  o = o || {};
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const t0 = Date.now(); let busyEver = false;
  const earlyEmpty = new Set();
  for (let i = 0; i < (o.maxWait || 70); i++) {
    const mm = document.querySelector(o.root || 'main') || document.body; const tx = mm.innerText || '';
    const busy = /Memuat|Loading\.\.\.|Sedang memuat/i.test(tx) || !!mm.querySelector('.animate-spin,[aria-busy="true"]') || tx.trim().length < 5;
    if (busy) { busyEver = true; (tx.match(/[^\n]{0,10}(?:Belum ada|Tidak ada)[^\n]{0,50}/g) || []).forEach((x) => earlyEmpty.add(x)); }
    const ents = performance.getEntriesByType('resource').filter((e) => /:8063\//.test(e.name));
    const lastEnd = ents.length ? Math.max(...ents.map((e) => e.responseEnd || e.startTime)) : 0;
    const quiet = performance.now() - lastEnd > (o.quiet || 1500);
    if (!busy && quiet && i >= (o.minWait || 4)) break;
    await sleep(300);
  }
  const loadMs = Date.now() - t0;
  const root = o.root ? document.querySelector(o.root) : (document.querySelector('main') || document.body);
  if (!root) return { err: 'no root ' + o.root };
  const W = innerWidth;
  const vis = (e) => { const r = e.getBoundingClientRect(); if (r.width <= 0 || r.height <= 0) return false; const cs = getComputedStyle(e); return cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity > 0; };
  const textEls = [...root.querySelectorAll('*')].filter((e) => { for (const n of e.childNodes) { if (n.nodeType === 3 && n.textContent.trim()) return vis(e); } return false; });
  const fs = textEls.map((e) => parseFloat(getComputedStyle(e).fontSize));
  const lt12 = fs.filter((f) => f < 12).length;
  const btn = [...root.querySelectorAll('button,[role=button],a[class*=button]')].filter(vis).map((b) => { const r = b.getBoundingClientRect(); return { h: Math.round(r.height), w: Math.round(r.width), t: (b.innerText || b.getAttribute('aria-label') || b.title || '').trim().replace(/\s+/g, ' ').slice(0, 28) }; });
  const cnt = (arr, f) => arr.filter(f).length;
  const inp = [...root.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]),select,textarea')].filter(vis).map((i) => { const r = i.getBoundingClientRect(); return { h: Math.round(r.height), w: Math.round(r.width), p: (i.placeholder || i.getAttribute('aria-label') || i.name || '').slice(0, 40), fs: parseFloat(getComputedStyle(i).fontSize) }; });
  const txt = (root.innerText || '').replace(/\n{2,}/g, '\n');
  const res = {
    v: new URLSearchParams(location.search).get('view'), e: localStorage.getItem('kn_entity'),
    u: (JSON.parse(localStorage.getItem('kn_user') || '{}').email || '').split('@')[0], W, loadMs,
    tNav: Math.round(performance.now()), busyEver,
    heads: [...root.querySelectorAll('h1,h2,h3')].filter(vis).slice(0, 6).map((h) => h.innerText.trim().slice(0, 50)),
    hub: [...document.querySelectorAll('.hub-tabs .tab-button')].map((b) => (b.classList.contains('active') ? '*' : '') + b.innerText.trim()),
    ptabs: [...new Set([...root.querySelectorAll('.page-tabs .tab-button,[role=tab]')].filter(vis).map((b) => (b.classList.contains('active') || b.getAttribute('aria-selected') === 'true' ? '*' : '') + b.innerText.trim().replace(/\s+/g, ' ').slice(0, 30)))].slice(0, 14),
    txtN: fs.length, lt12, pct12: fs.length ? Math.round(100 * lt12 / fs.length) : 0, minFs: fs.length ? Math.min(...fs) : null,
    btnN: btn.length, b24: cnt(btn, (b) => b.h < 24), b32: cnt(btn, (b) => b.h < 32), b36: cnt(btn, (b) => b.h < 36),
    b44: cnt(btn, (b) => b.h < 44 || b.w < 44), b48: cnt(btn, (b) => b.h < 48 || b.w < 48), bMinH: btn.length ? Math.min(...btn.map((b) => b.h)) : null,
    inpN: inp.length, i36: cnt(inp, (i) => i.h < 36), i48: cnt(inp, (i) => i.h < 48), iMinFs: inp.length ? Math.min(...inp.map((i) => i.fs)) : null,
    search: inp.filter((i) => /cari|search|nomor|kode|pindai|scan/i.test(i.p)).map((i) => i.p),
    chips: root.querySelectorAll('.filter-chip').length, pager: /Menampilkan \d/.test(txt),
    exportBtns: btn.filter((b) => /ekspor|export|csv|excel|xlsx|unduh/i.test(b.t)).map((b) => b.t),
    tables: [...root.querySelectorAll('table')].filter(vis).map((t) => t.rows.length),
    sortTh: [...root.querySelectorAll('th')].filter((t) => vis(t) && (t.getAttribute('aria-sort') || t.querySelector('button') || getComputedStyle(t).cursor === 'pointer')).length,
    thN: [...root.querySelectorAll('th')].filter(vis).length,
    earlyEmpty: [...earlyEmpty].slice(0, 3),
    rawIds: [...new Set((txt.match(/\b(?:ent|site|wh|bin|prod|roll|usr|user|loc|dev|task|grn|ins|var|cust|sup|mko|pa|tr|rfid|epc)_[a-z0-9_]{4,}\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi) || []))].slice(0, 8),
    testData: [...new Set((txt.match(/[^\n]{0,20}(?:TEST[_/ -]|Uji Provisioning|UJI-|iter_?\d+|\btest\b)[^\n]{0,25}/g) || []))].slice(0, 6),
    errs: [...new Set((txt.match(/[^\n]{0,40}(?:gagal|ditolak|Permission|Forbidden|tidak punya akses|tidak diizinkan|Error|error|kesalahan|Not Found|\[object)[^\n]{0,40}/g) || []))].slice(0, 5),
    empty: [...new Set((txt.match(/[^\n]{0,10}(?:Belum ada|Tidak ada|kosong|Tak ada)[^\n]{0,50}/g) || []))].slice(0, 5),
    english: [...new Set((txt.match(/\b(?:Loading|Submit|Cancel|Save|Delete|Search|Filter|No data|Warehouse|Location|Pending|Approved|Rejected|Draft|Received|Shipped|Dispatched|Picking|Packing|Putaway|Cycle Count|Reader|Settings|Export|Import|Upload|Download|Inbound|Outbound|Picker|Lead time|Stock|Supplier|Repair|Return|Claim|Order)\b/g) || []))].slice(0, 14),
    hx: document.documentElement.scrollWidth > W + 1,
  };
  if (o.text) { let t = txt; const hl = res.hub.map((h) => h.replace(/^\*/, '')); if (hl.length) t = t.replace(hl.join('\n') + '\n', ''); res.text = t.slice(0, o.text); }
  if (o.btns) res.btns = btn.slice(0, o.btns);
  if (o.inps) res.inps = inp.slice(0, o.inps);
  return res;
};

window.__b1bLogin = async function (email, pw, ent) {
  const ctl = new AbortController(); setTimeout(() => ctl.abort(), 25000);
  const api = (window.__b1bApi || 'http://localhost:8063/api');
  const r = await fetch(api + '/auth/login', { signal: ctl.signal, method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password: pw }), credentials: 'include' });
  const d = await r.json(); if (!r.ok) return { status: r.status, d };
  const u = { ...d.user, permissions: d.permissions || {}, role_label: d.role_label || (d.user && d.user.role) || '' };
  localStorage.setItem('kn_token', d.token); localStorage.setItem('kn_user', JSON.stringify(u));
  const ec = d.entity_context || {}; localStorage.setItem('kn_entity_ctx', JSON.stringify(ec));
  const prev = localStorage.getItem('kn_entity');
  const def = ent || ec.home_entity_id || (ec.entities && ec.entities[0] && ec.entities[0].id) || 'all';
  localStorage.setItem('kn_entity', def);
  if (window.__b1bGo) location.href = window.__b1bGo;
  return { role: u.role, label: u.role_label, prevEntity: prev, setEntity: def, home: ec.home_entity_id, can: ec.can_switch_entity, ents: (ec.entities || []).map((x) => x.code || x.short_name || x.id), sites: u.location_site_ids };
};

window.__s = async function (o) {
  o = o || {}; const r = await window.__b1b(Object.assign({ text: o.text || 140 }, o)); const L = (a) => (a && a.length ? a.length : 0);
  const parts = [r.v + (r.v !== o.want && o.want ? ' (≠' + o.want + ')' : ''), r.u, r.e, 't' + r.tNav, 'txt<12:' + r.pct12 + '%/' + r.txtN + ' min' + r.minFs,
    'btn' + r.btnN + ' <24:' + r.b24 + ' <36:' + r.b36 + ' <44:' + r.b44 + ' <48:' + r.b48 + ' minH' + r.bMinH,
    'inp' + r.inpN + (r.inpN ? ' <36:' + r.i36 + ' <48:' + r.i48 + ' fs' + r.iMinFs : ''), 'cari:' + L(r.search), 'chip:' + r.chips,
    'pager:' + (r.pager ? 1 : 0), 'eks:' + (r.exportBtns.join('/') || 0), 'tbl:' + r.tables.join('/'), 'th:' + r.thN + ' urut:' + r.sortTh, 'hx:' + (r.hx ? 1 : 0)];
  if (r.rawIds.length) parts.push('ID:' + r.rawIds.slice(0, 4).join(','));
  if (r.testData.length) parts.push('UJI:' + r.testData.slice(0, 3).join(' ¦ '));
  if (r.errs.length) parts.push('ERR:' + r.errs.slice(0, 3).join(' ¦ '));
  if (r.earlyEmpty.length) parts.push('KOSONG-PALSU:' + r.earlyEmpty.join(' ¦ '));
  if (r.english.length) parts.push('EN:' + r.english.join(','));
  if (r.empty.length) parts.push('KOSONG:' + r.empty.slice(0, 2).join(' ¦ '));
  parts.push('H:' + (r.heads[0] || '')); if (r.ptabs.length) parts.push('TAB:' + r.ptabs.join(','));
  parts.push('»' + (r.text || '').replace(/\n/g, ' | '));
  return parts.join(' · ');
};

window.__h = async function (o) {
  o = o || {}; const r = await window.__b1b(Object.assign({ text: o.text || 90 }, o));
  const sw = document.documentElement.scrollWidth;
  const wide = [...document.querySelectorAll('main table')].filter((t) => t.getBoundingClientRect().width > innerWidth + 1).length;
  return [r.v + (o.want && r.v !== o.want ? '(≠' + o.want + ')' : ''), r.u, 't' + r.tNav, 'txt<12:' + r.pct12 + '%', 'min' + r.minFs,
    'btn' + r.btnN + ' <44:' + r.b44 + ' <48:' + r.b48, 'inp<48:' + r.i48 + '/' + r.inpN, 'hx:' + (r.hx ? ('YA sw' + sw) : '0'),
    'tblLebar:' + wide + '/' + r.tables.length, r.errs.length ? 'ERR:' + r.errs.slice(0, 2).join('¦') : '', '»' + (r.text || '').replace(/\n/g, ' | ')]
    .filter(Boolean).join(' · ');
};

window.__hp = async function (o) {
  o = o || {}; const sleep = (ms) => new Promise((r) => setTimeout(r, ms)); const out = [];
  const tb = [...document.querySelectorAll('nav.m-tabbar button')]; const names = tb.map((b) => b.innerText.trim().replace(/\s+/g, ' '));
  const vis = (e) => { const r = e.getBoundingClientRect(); if (r.width <= 0 || r.height <= 0) return false; const cs = getComputedStyle(e); return cs.visibility !== 'hidden' && cs.display !== 'none'; };
  for (const [i, b] of tb.entries()) {
    if (o.only && !o.only.includes(i)) continue;
    b.click(); await sleep(o.wait || 2500);
    for (let k = 0; k < 20; k++) { if (!/Memuat/.test(document.body.innerText)) break; await sleep(300); }
    const root = document.querySelector('[data-testid=mobile-warehouse-app],[data-testid=mobile-ops-app],[data-testid$=-app]') || document.body;
    const btn = [...root.querySelectorAll('button,a[href],[role=button]')].filter(vis).map((x) => { const r = x.getBoundingClientRect(); return { h: Math.round(r.height), w: Math.round(r.width), t: (x.innerText || x.getAttribute('aria-label') || '').trim().slice(0, 22) }; });
    const te = [...root.querySelectorAll('*')].filter((e) => { for (const n of e.childNodes) { if (n.nodeType === 3 && n.textContent.trim()) return vis(e); } return false; });
    const fs = te.map((e) => parseFloat(getComputedStyle(e).fontSize));
    const inp = [...root.querySelectorAll('input:not([type=hidden]),select,textarea')].filter(vis).map((x) => { const r = x.getBoundingClientRect(); return Math.round(r.height) + '/' + parseFloat(getComputedStyle(x).fontSize); });
    const small = btn.filter((x) => x.h < 48 || x.w < 48); const t = document.body.innerText;
    out.push({ tab: names[i], txt12: Math.round(100 * fs.filter((f) => f < 12).length / Math.max(1, fs.length)) + '%/' + fs.length,
      lt14: Math.round(100 * fs.filter((f) => f < 14).length / Math.max(1, fs.length)) + '%', minFs: Math.min(...fs), btn: btn.length,
      b48: small.length, b44: btn.filter((x) => x.h < 44 || x.w < 44).length, smallEx: [...new Set(small.map((x) => x.t + ':' + x.w + 'x' + x.h))].slice(0, 6),
      inp, hx: document.documentElement.scrollWidth > innerWidth + 1,
      err: (t.match(/[^\n]{0,30}(Permission|ditolak|gagal|Gagal)[^\n]{0,30}/g) || []).slice(0, 2),
      text: (root.innerText || '').replace(/\n+/g, ' | ').slice(0, o.text || 260) });
  }
  return { W: innerWidth, appbar: (document.querySelector('.m-appbar') || {}).innerText,
    tabs: names.map((n, i) => { const r = tb[i].getBoundingClientRect(); return n + ':' + Math.round(r.width) + 'x' + Math.round(r.height); }), out };
};

window.__dlg = async function (o) {
  o = o || {}; const sleep = (ms) => new Promise((r) => setTimeout(r, ms)); await sleep(o.wait || 1500);
  const d = [...document.querySelectorAll('[role=dialog],.modal,[class*=modal-panel],[class*=drawer]')].filter((e) => e.getBoundingClientRect().height > 50).pop();
  if (!d) return 'TIDAK ADA DIALOG';
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const te = [...d.querySelectorAll('*')].filter((e) => { for (const n of e.childNodes) { if (n.nodeType === 3 && n.textContent.trim()) return vis(e); } return false; });
  const fs = te.map((e) => parseFloat(getComputedStyle(e).fontSize));
  const btn = [...d.querySelectorAll('button')].filter(vis).map((b) => { const r = b.getBoundingClientRect(); return (b.innerText || b.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 18) + ':' + Math.round(r.width) + 'x' + Math.round(r.height); });
  const r = d.getBoundingClientRect();
  const out = 'DLG ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' · txt<12 ' + Math.round(100 * fs.filter((f) => f < 12).length / Math.max(1, fs.length)) + '%/' + fs.length + ' min' + Math.min(...fs) + ' · btn: ' + btn.slice(0, o.nb || 14).join(', ') + ' · »' + d.innerText.replace(/\n+/g, ' | ').slice(0, o.text || 300);
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  d.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  await sleep(600);
  const still = [...document.querySelectorAll('[role=dialog]')].filter((e) => e.getBoundingClientRect().height > 50).length;
  return out + ' · ESC-tutup:' + (still ? 'TIDAK' : 'ya');
};
