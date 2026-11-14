// Potret Meja Finance (finance@) di 1280 & 390 px + ukur apakah tombol "Bantuan & Panduan" menutupi isi.
// node potret_meja_finance.js <label> [outdir]  → <label>-1280(.png|-top.png|-bottom.png), <label>-390…, <label>-report.json
// MOCK_DESK=desk_mockA.json → jawaban /api/finance/desk dicegat (data rekayasa, DB tidak disentuh).
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const label = process.argv[2] || "before";
const outDir = process.argv[3] || path.join(__dirname, "shots");
fs.mkdirSync(outDir, { recursive: true });
const BASE = "http://localhost:3000";

async function login(page) {
  await page.goto(BASE);
  await page.waitForSelector('[data-testid="login-email-input"]', { timeout: 60000 });
  await page.fill('[data-testid="login-email-input"]', "finance@kainnusantara.id");
  await page.fill('[data-testid="login-password-input"]', "demo12345");
  await page.click('[data-testid="login-submit-button"]');
  try { await page.waitForSelector('[data-testid="finance-desk"]', { timeout: 60000, state: "attached" }); }
  catch (e) { await page.screenshot({ path: path.join(outDir, "fail.png") }); console.log(page.url(), (await page.evaluate(() => document.body.innerText)).slice(0, 300)); throw e; }
  // antrean selesai dimuat (bukan keadaan "Menyusun antrean…")
  await page.waitForFunction(() => !document.querySelector('[data-testid="fin-desk-loading"]'), null, { timeout: 60000 });
  await page.waitForTimeout(2500);
  // Notifikasi "Login berhasil…" di topbar melebarkan halaman (bawaan, di luar lingkup) — tutup supaya potret sebanding.
  const close = page.locator(".topbar button", { hasText: "Tutup" });
  if (await close.count()) { await close.first().click().catch(() => {}); await page.waitForTimeout(400); }
}

async function measure(page) {
  return page.evaluate(() => {
    const btn = document.querySelector('[data-testid="help-tours-button"]');
    const fabWrap = btn && btn.closest(".tour-fab");          // null = tombol di topbar (tidak melayang)
    const r = fabWrap ? btn.getBoundingClientRect() : null;
    const queues = [...document.querySelectorAll('[data-testid^="fin-desk-queue-"]')]
      .filter((el) => /^fin-desk-queue-[a-z_]+$/.test(el.dataset.testid) && !el.dataset.testid.startsWith("fin-desk-queue-toggle"))
      .map((el) => { const b = el.getBoundingClientRect(); return { id: el.dataset.testid.replace("fin-desk-queue-", ""), top: Math.round(b.top + scrollY), left: Math.round(b.left), w: Math.round(b.width), h: Math.round(b.height) }; });
    const doc = document.scrollingElement;
    const covered = [];
    if (r) {
      for (const y of [r.top + 4, r.top + r.height / 2, r.bottom - 4]) {
        for (const x of [r.left + 4, r.left + r.width / 2, r.right - 4]) {
          fabWrap.style.visibility = "hidden";
          const under = document.elementFromPoint(x, y);
          fabWrap.style.visibility = "";
          const t = under && under.closest("[data-testid]");
          if (under && t && !["finance-desk", "main-content"].includes(t.dataset.testid) && under.textContent.trim())
            covered.push(`${t.dataset.testid}: ${under.textContent.trim().slice(0, 30)}`);
        }
      }
    }
    const boards = [...document.querySelectorAll('[data-testid^="fin-home-board-"]')]
      .filter((el) => /^fin-home-board-[a-z_]+$/.test(el.dataset.testid))
      .map((el) => ({ id: el.dataset.testid, h: Math.round(el.getBoundingClientRect().height) }));
    return { help: btn ? (fabWrap ? "melayang" : "topbar") : "tidak ada",
      fab: r && { top: Math.round(r.top), left: Math.round(r.left), w: Math.round(r.width), h: Math.round(r.height) },
      scrollY: Math.round(scrollY), scrollH: doc.scrollHeight, scrollW: doc.scrollWidth, innerH: innerHeight, queues, boards,
      covered: [...new Set(covered)],
      fold: !!document.querySelector('[data-testid="fin-desk-empty-fold"]') };
  });
}

(async () => {
  const browser = await chromium.launch();
  const report = {};
  for (const vp of [{ w: 1280, h: 800 }, { w: 390, h: 844 }]) {
    const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h }, deviceScaleFactor: 2 });
    // HP: peran Finance mendarat di aplikasi HP; Meja Finance dibuka lewat "Tampilan Desktop" (escape-hatch resmi).
    if (vp.w < 900) await ctx.addInitScript(() => { try { localStorage.setItem("kn_force_desktop", "1"); } catch (e) {} });
    const page = await ctx.newPage();
    if (process.env.MOCK_DESK) {
      const body = fs.readFileSync(process.env.MOCK_DESK, "utf8");
      await page.route("**/api/finance/desk*", (route) => route.fulfill({ status: 200, contentType: "application/json", body }));
    }
    await login(page);
    const deskTop = await page.evaluate(() => {
      const el = document.querySelector('[data-testid="finance-desk"]'); return el ? Math.round(el.getBoundingClientRect().top + scrollY) : 0;
    });
    const top = await measure(page);                            // tampilan pertama (belum digulir)
    await page.screenshot({ path: path.join(outDir, `${label}-${vp.w}-top.png`) });
    await page.screenshot({ path: path.join(outDir, `${label}-${vp.w}.png`), fullPage: true });
    // Akhir halaman (yang dilihat pengguna saat menggulir ke bawah) — widget mengapung ikut terpotret.
    await page.evaluate(() => window.scrollTo({ top: document.scrollingElement.scrollHeight, behavior: "instant" }));
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(outDir, `${label}-${vp.w}-bottom.png`) });
    const bottom = await measure(page);
    report[vp.w] = { deskTop, help: top.help, scrollH: top.scrollH, scrollW: top.scrollW, boards: top.boards, fold: top.fold,
      queues: top.queues, coveredTop: top.covered, coveredBottom: bottom.covered, fab: top.fab };
    await ctx.close();
  }
  fs.writeFileSync(path.join(outDir, `${label}-report.json`), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
