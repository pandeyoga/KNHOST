// Meja gelombang 2 — tangkapan sesudah: pratinjau dokumen di layar Keuangan + pop-up meja berisi rincian dokumen.
const { chromium } = require("playwright");
const fs = require("fs");
const OUT = __dirname + "/sesudah_mg2";
fs.mkdirSync(OUT, { recursive: true });
const BASE = "http://localhost:3000";
const log = [];
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
const previewOpen = (page) => page.locator('[data-testid="doc-preview"]').count();
async function closeAll(page) {
  for (let i = 0; i < 3; i++) { await page.keyboard.press("Escape").catch(() => {}); await page.waitForTimeout(300); }
}
// Klik tombol tautan di area utama satu per satu sampai pratinjau dokumen terbuka.
async function openPreview(page, tag, scope = "main") {
  const btns = page.locator(`${scope} button.link-button`);
  const n = Math.min(await btns.count(), 25);
  for (let i = 0; i < n; i++) {
    const b = btns.nth(i);
    if (!(await b.isVisible().catch(() => false))) continue;
    const txt = ((await b.innerText().catch(() => "")) || "").trim();
    if (!/[A-Z]{2,}[-/]|\d{3,}/.test(txt)) continue; // nomor dokumen, bukan nama pihak
    await b.click({ timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(1800);
    if (await previewOpen(page)) {
      await shot(page, `${tag}_pratinjau`);
      const lines = await page.locator('[data-testid="doc-preview-lines"] tbody tr').count().catch(() => 0);
      log.push(`${tag}: klik "${txt}" → pratinjau MUNCUL, baris barang ${lines}`);
      return true;
    }
    await closeAll(page);
  }
  log.push(`${tag}: pratinjau tidak terbuka (tak ada nomor berpratinjau di layar)`);
  return false;
}
async function view(page, v, wait = 6000) {
  await page.goto(`${BASE}/?view=${v}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(wait);
}
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  try {
    await login(page, "finance@kainnusantara.id");
    // Layar daftar Keuangan (§5.7a)
    for (const [v, tag] of [["tax-invoices", "11_faktur_keluaran"], ["collection-worklist", "12_penagihan"],
      ["cash-management", "13_transaksi_kas"], ["payment-plans", "14_rencana_bayar"]]) {
      try { await view(page, v); await shot(page, `${tag}_daftar`); await openPreview(page, tag); await closeAll(page); }
      catch (e) { log.push(`${tag}: GALAT ${e.message.slice(0, 140)}`); }
    }
    // Rincian yang perlu dibuka dulu: kontrabon, hutang per pemasok, piutang
    for (const [v, tag] of [["contra-bons", "15_kontrabon"], ["ap-by-supplier", "16_hutang_pemasok"], ["ar-aging", "17_piutang"]]) {
      try {
        await view(page, v);
        const row = page.locator("main tbody tr, main [data-testid*='-row-']").first();
        if (await row.count()) { await row.click({ timeout: 3000 }).catch(() => {}); await page.waitForTimeout(3000); }
        await shot(page, `${tag}_rincian`);
        await openPreview(page, tag, "body");
        await closeAll(page);
      } catch (e) { log.push(`${tag}: GALAT ${e.message.slice(0, 140)}`); }
    }
    // Meja Keuangan: pop-up baris berisi rincian dokumen
    await view(page, "finance-desk", 7000);
    const nums = page.locator('main button[data-testid*="-number-"]');
    const k = Math.min(await nums.count(), 6);
    for (let i = 0; i < k; i++) {
      await nums.nth(i).click({ timeout: 4000 }).catch(() => {});
      await page.waitForTimeout(2500);
      const panel = await page.locator('[data-testid$="-doc-panel"]').count();
      await shot(page, `18_meja_keuangan_popup_${i + 1}`);
      log.push(`meja keuangan baris ${i + 1}: pop-up ${panel ? "berisi rincian dokumen" : "panel umum"}`);
      await closeAll(page);
    }
  } catch (e) { log.push(`finance: GALAT ${e.message.slice(0, 160)}`); }
  await ctx.close();
  // Meja Admin Sales desktop
  const ctx2 = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const p2 = await ctx2.newPage();
  try {
    await login(p2, "salesadmin@kainnusantara.id");
    await view(p2, "sales-admin-desk", 7000);
    const nums = p2.locator('main button[data-testid*="-number-"]');
    const k = Math.min(await nums.count(), 4);
    for (let i = 0; i < k; i++) {
      await nums.nth(i).click({ timeout: 4000 }).catch(() => {});
      await p2.waitForTimeout(2500);
      const panel = await p2.locator('[data-testid$="-doc-panel"]').count();
      await shot(p2, `19_admin_sales_popup_${i + 1}`);
      log.push(`admin sales baris ${i + 1}: pop-up ${panel ? "berisi rincian dokumen" : "panel umum"}`);
      await closeAll(p2);
    }
  } catch (e) { log.push(`admin sales: GALAT ${e.message.slice(0, 160)}`); }
  await ctx2.close();
  // HP Admin Sales
  const ctx3 = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const p3 = await ctx3.newPage();
  try {
    await login(p3, "salesadmin@kainnusantara.id");
    await p3.waitForTimeout(4000);
    const nomor = p3.locator('button[data-testid^="m-desk-number-"]').first();
    if (await nomor.count()) {
      await nomor.click({ timeout: 4000 }).catch(() => {});
      await p3.waitForTimeout(2500);
      await shot(p3, "20_hp_admin_sales_popup", true);
      const jejak = await p3.locator('[data-testid="m-desk-doc-trace"]').count();
      log.push(`HP admin sales: pop-up dibuka; tombol Jejak ${jejak ? "ADA (salah)" : "tidak ada (benar)"}`);
    } else log.push("HP admin sales: tak ada baris");
  } catch (e) { log.push(`HP: GALAT ${e.message.slice(0, 160)}`); }
  await ctx3.close();
  await browser.close();
  fs.writeFileSync(`${__dirname}/tangkap_mg2_log.txt`, log.join("\n") + "\n");
  console.log(log.join("\n"));
})();
