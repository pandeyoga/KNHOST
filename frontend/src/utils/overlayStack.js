// Tumpukan pop-up global: pop-up yang dibuka BELAKANGAN selalu di atas yang lama.
// Dulu tiap layar menulis z-index sendiri (z-50 … z-[260]) sehingga pop-up anak bisa
// tertutup pop-up induk, dan dropdown ber-portal tertinggal di belakang modal.
const SEL = ".modal-overlay, .m-sheet-wrap, .fixed.inset-0";
const BASE = 1000;
let top = BASE;

function isDialogLayer(el) {
  if (el.classList.contains("modal-overlay") || el.classList.contains("m-sheet-wrap")) return true;
  return !!el.querySelector('[role="dialog"], .modal-card, .modal-panel, [data-testid$="-modal"], [data-testid$="-dialog"]')
    || /-(modal|dialog|overlay|sheet)$/.test(el.dataset.testid || "");
}

function bump(el) {
  if (el.nodeType !== 1 || el.dataset.stackZ || !el.matches?.(SEL) || !isDialogLayer(el)) return;
  top += 2;
  el.dataset.stackZ = String(top);
  el.style.zIndex = String(top);
}

export function installOverlayStack() {
  if (typeof window === "undefined" || window.__knOverlayStack) return;
  window.__knOverlayStack = true;
  new MutationObserver((muts) => {
    for (const m of muts) {
      m.addedNodes.forEach((n) => {
        if (n.nodeType !== 1) return;
        bump(n);
        n.querySelectorAll?.(SEL).forEach(bump);
      });
    }
    if (!document.querySelector("[data-stack-z]")) top = BASE;
  }).observe(document.body, { childList: true, subtree: true });
}
