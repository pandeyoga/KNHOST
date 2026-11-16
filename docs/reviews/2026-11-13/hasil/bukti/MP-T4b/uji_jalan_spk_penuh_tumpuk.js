const { chromium } = require("playwright");
const OUT = "/tmp/claude-0/-home-user-KNHOST/eae71b8b-a870-5a6b-a6d8-0d7c84ba5037/scratchpad/ui_m4b";
(async () => {
  const b = await chromium.launch({ args: ["--no-proxy-server"] });
  for (const w of [1366, 1280, 1024]) {
    const page = await (await b.newContext({ viewport: { width: w, height: 900 }, deviceScaleFactor: 1 })).newPage();
    await page.goto("http://localhost:3000/");
    await page.getByTestId("login-email-input").fill("admin@kainnusantara.id");
    await page.getByTestId("login-password-input").fill("demo12345");
    await page.getByTestId("login-submit-button").click();
    await page.waitForTimeout(3500);
    await page.goto("http://localhost:3000/?view=gr-ir");
    await page.waitForTimeout(3500);
    await page.locator('input[data-testid="grir-search"], [data-testid="grir-search"] input').first().fill(process.argv[2]);
    await page.waitForTimeout(2500);
    await page.locator('[data-testid^="grir-open-mko-"]').first().click();
    await page.waitForTimeout(4000);
    const backs = await page.locator('text=/Kembali/').allInnerTexts();
    console.log(w, "teks Kembali:", JSON.stringify(backs));
    await page.screenshot({ path: `${OUT}/spk-${w}-penuh.png`, fullPage: true });
    // Deteksi teks bertumpuk: elemen teks daun yang kotaknya saling menimpa
    const tumpuk = await page.evaluate(() => {
      const els = [...document.querySelectorAll(".view-container *, [data-testid] *")].filter((e) => e.children.length === 0 && e.textContent.trim() && e.offsetParent && !e.closest("details:not([open]) > :not(summary)") && !e.closest("aside, nav, header"));
      const boxes = els.map((e) => ({ t: e.textContent.trim().slice(0, 40), r: e.getBoundingClientRect() })).filter((x) => x.r.width > 0 && x.r.height > 0);
      const out = [];
      for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i].r, c = boxes[j].r;
        const ox = Math.min(a.right, c.right) - Math.max(a.left, c.left), oy = Math.min(a.bottom, c.bottom) - Math.max(a.top, c.top);
        if (ox > 4 && oy > 4) out.push(`${boxes[i].t} ⟂ ${boxes[j].t}`);
      }
      return [...new Set(out)].slice(0, 30);
    });
    console.log(w, "bertumpuk:", tumpuk.length, JSON.stringify(tumpuk));
    if (w === 1280) {
      await page.getByTestId("mko-ledger-details-toggle").click();
      await page.waitForTimeout(500);
      await page.getByTestId("mko-material-ledger").screenshot({ path: `${OUT}/spk-1280-bukubahan-dibuka.png` });
    }
    await page.context().close();
  }
  await b.close();
})();
