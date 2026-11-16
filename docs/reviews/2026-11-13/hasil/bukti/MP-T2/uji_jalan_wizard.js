// MP-T2 U4 — pintu Pesanan Pembelian membuka wizard yang sama; "Isi dari rute utama"; pilihan tahap tersaring.
const { chromium } = require("playwright");
const OUT = "/tmp/claude-0/-home-user-KNHOST/eae71b8b-a870-5a6b-a6d8-0d7c84ba5037/scratchpad/ui_wizard";
require("fs").mkdirSync(OUT, { recursive: true });
const BASE = "http://localhost:3000";
const log = (...a) => console.log(...a);

async function login(page) {
  await page.goto(BASE + "/");
  await page.getByTestId("login-email-input").fill("admin@kainnusantara.id");
  await page.getByTestId("login-password-input").fill("demo12345");
  await page.getByTestId("login-submit-button").click();
  await page.waitForTimeout(3500);
}
async function pick(page, triggerTid, text) {
  await page.getByTestId(triggerTid).click();
  await page.waitForTimeout(600);
  await page.keyboard.type(text);
  await page.waitForTimeout(1500);
  await page.locator('[data-testid^="product-select-item-"]').first().click();
  await page.waitForTimeout(800);
}
async function comboOptions(page, tid) {
  await page.getByTestId(tid).click();
  await page.waitForTimeout(700);
  const o = (await page.locator('[role="option"]').allInnerTexts()).map((t) => t.replace(/\s+/g, " ").trim());
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  return o;
}

(async () => {
  const browser = await chromium.launch({ args: ["--no-proxy-server"] });
  for (const [w, h, tag] of [[1280, 900, "1280"], [390, 844, "390"]]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h } });
    const page = await ctx.newPage();
    const errors = [];
    page.on("response", (r) => { if (r.status() >= 400 && r.url().includes("/api/")) errors.push(`${r.status()} ${r.url().replace(/.*\/api/, "/api").slice(0, 90)}`); });
    await login(page);
    if (tag === "1280") {
      await page.goto(BASE + "/?view=purchase-orders");
      await page.waitForTimeout(3500);
      await page.getByTestId("create-po-button").click();
      await page.waitForTimeout(600);
      await page.getByTestId("procure-mode-menu").locator('[role="menuitem"]').nth(2).click();
    } else {
      await page.goto(BASE + "/?view=makloon-orders");
      await page.waitForTimeout(3500);
      await page.locator("button", { hasText: "Buat Order Makloon" }).first().click();
    }
    await page.waitForTimeout(2000);
    log(`[${tag}] judul pop-up:`, await page.getByTestId("makloon-wizard-title").innerText());
    await pick(page, "wizard-route-product", "AUD-RND-5266D");
    await page.getByTestId("wizard-route-qty").fill("300");
    await page.getByTestId("wizard-route-apply").click();
    await page.waitForTimeout(1500);
    log(`[${tag}] catatan rute:`, await page.getByTestId("wizard-route-note").innerText().catch(() => "(tidak ada)"));
    log(`[${tag}] bahan:`, await page.getByTestId("wizard-material").innerText(), "qty", await page.getByTestId("wizard-material-qty").inputValue());
    await page.screenshot({ path: `${OUT}/${tag}-01-isi-rute.png` });
    await page.getByTestId("wizard-manual-material-reason").fill("uji jalan MP-T2").catch(() => {});
    await page.getByTestId("wizard-next").click();
    await page.waitForTimeout(2500);
    log(`[${tag}] langkah 1 tahap terpilih:`, await page.getByTestId("wizard-stage-1").innerText());
    log(`[${tag}] pilihan tahap langkah 1 (bahan Greige):`, (await comboOptions(page, "wizard-stage-1")).join(" | "));
    log(`[${tag}] pilihan tahap langkah 2 (sesudah PFP):`, (await comboOptions(page, "wizard-stage-2")).join(" | "));
    await page.screenshot({ path: `${OUT}/${tag}-02-rantai.png`, fullPage: tag === "390" });
    if (tag === "390") log("390 scrollWidth:", await page.evaluate(() => document.documentElement.scrollWidth));
    log(`[${tag}] galat API:`, [...new Set(errors)].join(" ; ") || "-");
    await ctx.close();
  }
  await browser.close();
})();
