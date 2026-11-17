// Render diagram alur (src/ppt/alur/*.html → *.png) untuk deck PowerPoint.
//   node docs/pelatihan/2026-11-18_keuangan/src/ppt/render_alur.js
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

(async () => {
  const dir = path.join(__dirname, "alur");
  const b = await chromium.launch({ args: ["--no-proxy-server"] });
  const page = await b.newPage({ viewport: { width: 1520, height: 900 }, deviceScaleFactor: 2 });
  for (const f of fs.readdirSync(dir).filter((x) => x.endsWith(".html"))) {
    await page.goto("file://" + path.join(dir, f));
    await page.locator("#d").screenshot({ path: path.join(dir, f.replace(/\.html$/, ".png")) });
  }
  await b.close();
  console.log("diagram alur dirender:", fs.readdirSync(dir).filter((x) => x.endsWith(".png")).length);
})();
