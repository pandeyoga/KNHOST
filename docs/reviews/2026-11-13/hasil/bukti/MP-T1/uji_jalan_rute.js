// MP-T1 U13 — uji jalan tab Rute: buka induk, buat rute 2 langkah (PFP @ pretreat → Printing @ Rotary), potret 1280 & 390.
const { chromium } = require("playwright");
const OUT = "/tmp/claude-0/-home-user-KNHOST/eae71b8b-a870-5a6b-a6d8-0d7c84ba5037/scratchpad/ui_rute";
require("fs").mkdirSync(OUT, { recursive: true });
const BASE = "http://localhost:3000";
const ART = process.argv[2] || "Kain Audit labdip 5266D";
const log = (...a) => console.log(...a);

async function login(page) {
  await page.goto(BASE + "/");
  await page.getByTestId("login-email-input").fill("md@kainnusantara.id");
  await page.getByTestId("login-password-input").fill("demo12345");
  await page.getByTestId("login-submit-button").click();
  await page.waitForTimeout(3500);
}
async function openArticle(page) {
  await page.goto(BASE + "/?view=md-products");
  await page.waitForTimeout(3500);
  const search = page.getByTestId("catalog-search");
  await search.fill(ART);
  await page.waitForTimeout(2000);
  await page.getByText(ART).first().click();
  await page.waitForTimeout(2500);
  await page.getByTestId("catalog-tab-routes").click();
  await page.waitForTimeout(2000);
}
const opts = async (page, tid) => (await page.getByTestId(tid).locator("option").allInnerTexts()).map((t) => t.trim());

(async () => {
  const browser = await chromium.launch({ args: ["--no-proxy-server"] });
  const errors = [];
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  page.on("response", (r) => { if (r.status() >= 400 && r.url().includes("/api/")) errors.push(`${r.status()} ${r.url().replace(/.*\/api/, "/api").slice(0, 100)}`); });
  await login(page);
  await openArticle(page);
  await page.screenshot({ path: `${OUT}/1280-01-kosong.png` });
  log("teks tab:", (await page.getByTestId("catalog-routes").innerText()).replace(/\s+/g, " ").slice(0, 300));
  await page.getByTestId("route-create").click();
  await page.waitForTimeout(1200);
  await page.getByTestId("route-name").fill("Printing di Rotary (uji jalan)");
  log("langkah 1 tahap:", (await opts(page, "route-step-1-stage")).join(" | "));
  await page.getByTestId("route-step-1-stage").selectOption("pfp");
  log("langkah 1 mitra (pfp):", (await opts(page, "route-step-1-partner")).join(" | "));
  await page.getByTestId("route-step-1-partner").selectOption("mak_seed_pretreat");
  await page.getByTestId("route-add-step").click();
  await page.waitForTimeout(500);
  log("langkah 2 tahap (sesudah PFP):", (await opts(page, "route-step-2-stage")).join(" | "));
  await page.getByTestId("route-step-2-stage").selectOption("printing");
  log("langkah 2 mitra (printing):", (await opts(page, "route-step-2-partner")).join(" | "));
  await page.getByTestId("route-step-2-partner").selectOption("mak_seed_printing");
  await page.screenshot({ path: `${OUT}/1280-02-form.png` });
  await page.getByTestId("route-form-submit").click().catch(async () => { await page.getByRole("button", { name: "Buat rute" }).last().click(); });
  await page.waitForTimeout(2000);
  log("sesudah simpan:", (await page.getByTestId("catalog-routes").innerText()).replace(/\s+/g, " ").slice(0, 400));
  await page.screenshot({ path: `${OUT}/1280-03-tersimpan.png` });
  // rute yang melompat tahap: langkah printing langsung — pilihan tahap langkah 1 tetap semua; uji pesan server
  await page.getByTestId("route-create").click();
  await page.waitForTimeout(1000);
  await page.getByTestId("route-name").fill("Salah: hanya PFP");
  await page.getByTestId("route-step-1-stage").selectOption("pfp");
  await page.getByTestId("route-form-submit").click().catch(() => {});
  await page.waitForTimeout(1500);
  log("galat server di pop-up:", (await page.getByTestId("route-form").innerText()).replace(/\s+/g, " ").match(/Rute berakhir[^.]*\./)?.[0] || "(tidak terlihat)");
  await page.screenshot({ path: `${OUT}/1280-04-galat.png` });
  await page.keyboard.press("Escape");
  await ctx.close();
  const m = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  const p2 = await m.newPage();
  await login(p2);
  await openArticle(p2);
  await p2.screenshot({ path: `${OUT}/390-01-daftar.png`, fullPage: true });
  await p2.getByTestId("route-create").click();
  await p2.waitForTimeout(1000);
  await p2.screenshot({ path: `${OUT}/390-02-form.png` });
  const sw = await p2.evaluate(() => document.documentElement.scrollWidth);
  log("390 scrollWidth:", sw);
  log("galat API:", [...new Set(errors)].join(" ; ") || "-");
  await browser.close();
})();
