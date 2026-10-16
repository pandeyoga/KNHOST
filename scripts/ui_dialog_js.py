JS_DIALOG = r"""
() => {
  const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const dlg = [...document.querySelectorAll('[role="dialog"], .modal-card, .modal-panel')].filter(vis).pop();
  if (!dlg) return null;
  const r = dlg.getBoundingClientRect();
  const out = { w: Math.round(r.width), h: Math.round(r.height), issues: [] };
  if (r.width > window.innerWidth - 8) out.issues.push("lebar penuh layar");
  if (r.right > window.innerWidth + 2 || r.left < -2) out.issues.push("keluar layar horizontal");
  const txt = dlg.innerText || "";
  [/\bNaN\b/, /\bundefined\b/, /\[object Object\]/, /Invalid Date/, /TEST_|iter1\d\d/].forEach((p) => { const m = txt.match(p); if (m) out.issues.push("teks: " + m[0]); });
  const fields = [...dlg.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]), textarea, button[role=combobox]')].filter(vis);
  for (let i = 0; i < fields.length; i++) {
    const a = fields[i].getBoundingClientRect();
    if (a.right > r.right + 2) { out.issues.push("field meluber: " + (fields[i].getAttribute("data-testid") || fields[i].name || i)); break; }
    for (let j = i + 1; j < fields.length; j++) {
      const b = fields[j].getBoundingClientRect();
      if (a.left < b.right - 2 && b.left < a.right - 2 && a.top < b.bottom - 2 && b.top < a.bottom - 2) {
        out.issues.push("field tumpang tindih: " + (fields[i].getAttribute("data-testid") || i) + " × " + (fields[j].getAttribute("data-testid") || j)); i = fields.length; break;
      }
    }
  }
  const nat = [...dlg.querySelectorAll('button')].filter((b) => vis(b) && getComputedStyle(b).backgroundColor === 'rgb(239, 239, 239)').length;
  if (nat) out.issues.push(nat + " tombol tanpa gaya");
  const sel = [...dlg.querySelectorAll('select')].filter((s) => vis(s) && !s.className).length;
  if (sel) out.issues.push(sel + " select bawaan tanpa gaya");
  return out;
}
"""
JS_OPENERS = r"""
() => {
  const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  return [...document.querySelectorAll('main button')].filter((b) => vis(b) && !b.disabled && b.getAttribute('data-testid')
    && /^(\+\s*)?(Buat|Tambah|Baru|Catat|Ajukan|Input|Daftarkan|Rekam|Terbitkan)/i.test((b.innerText || '').trim()))
    .slice(0, 3).map((b) => b.getAttribute('data-testid'));
}
"""
