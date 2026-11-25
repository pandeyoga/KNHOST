// Meja gelombang 1 — tangkapan SESUDAH (bandingkan dengan docs/audit/meja-2026-11-25/tangkapan/01–10).
const { chromium } = require("playwright");
const fs = require("fs");
const OUT = __dirname + "/sesudah";
fs.mkdirSync(OUT, { recursive: true });
const BASE = "http://localhost:3000";
const DESKTOP = [
  ["salesadmin@kainnusantara.id", "sales-admin-desk", "01_admin_sales"],
  ["finance@kainnusantara.id", "finance-desk", "02_meja_keuangan"],
  ["manager@kainnusantara.id", "my-desk", "03_meja_saya_manajer"],
  ["sales@kainnusantara.id", "my-desk", "04_meja_saya_sales"],
  ["md@kainnusantara.id", "md-desk", "05_meja_md"],
  ["whadmin@kainnusantara.id", "warehouse-admin-desk", "06_meja_gudang"],
  ["sampleadmin@kainnusantara.id", "sample-admin-desk", "07_meja_sample"],
];
const MOBILE = [["salesadmin@kainnusantara.id", "08_hp_admin_sales"], ["md@kainnusantara.id", "10_hp_md"]];
const clean = (p) => p.evaluate(() => document.querySelectorAll("iframe#webpack-dev-server-client-overlay").forEach((e) => e.remove())).catch(() => {});
async function login(page, email) {
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-testid="login-email-input"]', { timeout: 90000 });
  await page.fill('[data-testid="login-email-input"]', email);
  await page.fill('[data-testid="login-password-input"]', "demo12345");
  await page.click('[data-testid="login-submit-button"]');
  await page.waitForTimeout(4000);
}
async function shot(page, name, full = false) {
  await clean(page);
  await page.screenshot({ path: `${OUT}/${name}.jpg`, type: "jpeg", quality: 72, fullPage: full });
}
(async () => {
  const browser = await chromium.launch();
  const log = [];
  for (const [email, view, tag] of DESKTOP) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    try {
      await login(page, email);
      await page.goto(`${BASE}/?view=${view}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(7000);
      await shot(page, `${tag}_antrean`, true);
      const h = await page.evaluate(() => document.documentElement.scrollHeight);
      // tinggi kartu antrean (harus sama semua)
      const tinggi = await page.evaluate(() => [...document.querySelectorAll("main section, main [class*='section-card']")]
        .filter((e) => /sm:h-\[412px\]/.test(e.className)).map((e) => Math.round(e.getBoundingClientRect().height)));
      log.push(`${tag}: tinggi halaman ${h}px (${(h / 900).toFixed(1)} layar); kartu tetap ${tinggi.length} buah, tinggi unik ${[...new Set(tinggi)].join("/")}`);
      // klik nomor dokumen pertama → pop-up rincian
      const nomor = page.locator('main button[data-testid*="-number-"]').first();
      if (await nomor.count()) {
        await nomor.click({ timeout: 5000 }).catch(() => {});
        await page.waitForTimeout(1500);
        const dlg = await page.locator('[role="dialog"], .kn-modal-overlay').count();
        log.push(`${tag}: klik nomor → pop-up ${dlg ? "MUNCUL" : "tidak muncul"}; url ${page.url().replace(BASE, "")}`);
        await shot(page, `${tag}_popup`);
        await page.keyboard.press("Escape").catch(() => {});
        await page.waitForTimeout(800);
      } else log.push(`${tag}: tidak ada baris antrean berisi`);
      // tab Pantau (di meja; untuk Keuangan = tab hub)
      const pantau = page.locator('[role="tab"], button').filter({ hasText: /^\s*Pantau\s*$/ }).first();
      if (await pantau.count()) {
        await pantau.click({ timeout: 5000 }).catch(() => {});
        await page.waitForTimeout(4000);
        await shot(page, `${tag}_pantau`, true);
        log.push(`${tag}: tab Pantau dibuka`);
      } else log.push(`${tag}: tab Pantau tidak ditemukan`);
    } catch (e) { log.push(`${tag}: GALAT ${e.message.slice(0, 160)}`); }
    await ctx.close();
  }
  for (const [email, tag] of MOBILE) {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const page = await ctx.newPage();
    try {
      await login(page, email);
      await page.waitForTimeout(5000);
      await shot(page, `${tag}`, true);
      const h = await page.evaluate(() => document.documentElement.scrollHeight);
      log.push(`${tag}: tinggi halaman ${h}px (${(h / 844).toFixed(1)} layar)`);
      const nomor = page.locator('button[data-testid^="m-desk-number-"], button[data-testid*="-number-"]').first();
      if (await nomor.count()) {
        await nomor.click({ timeout: 5000 }).catch(() => {});
        await page.waitForTimeout(1500);
        await shot(page, `${tag}_popup`);
        log.push(`${tag}: pop-up HP ${await page.locator('[role="dialog"], .kn-modal-overlay').count() ? "MUNCUL" : "tidak muncul"}`);
      }
    } catch (e) { log.push(`${tag}: GALAT ${e.message.slice(0, 160)}`); }
    await ctx.close();
  }
  await browser.close();
  fs.writeFileSync(`${__dirname}/tangkap_sesudah_log.txt`, log.join("\n") + "\n");
  console.log(log.join("\n"));
})();
